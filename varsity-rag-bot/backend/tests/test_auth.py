import asyncio
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from httpx import Request, Response
from fastapi.testclient import TestClient
from groq import APIStatusError
from jose import jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.core.config import Settings
from backend.app.core.database import get_db
from backend.app.main import app
from backend.app.models import Base, ChatLog, User, UserRole


class SettingsTests(unittest.TestCase):
    def test_render_postgres_url_uses_asyncpg_driver(self) -> None:
        for database_url in (
            "postgres://user:password@host:5432/eu_ai",
            "postgresql://user:password@host:5432/eu_ai",
        ):
            with self.subTest(database_url=database_url):
                settings = Settings(database_url=database_url)

                self.assertEqual(
                    settings.database_url,
                    "postgresql+asyncpg://user:password@host:5432/eu_ai",
                )


class AuthenticationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_directory.name) / "auth-test.db"
        self.engine = create_async_engine(
            f"sqlite+aiosqlite:///{database_path.as_posix()}"
        )
        asyncio.run(self._create_schema())
        self.session_factory = async_sessionmaker(
            self.engine, expire_on_commit=False
        )

        async def override_get_db():
            async with self.session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        self.environment = patch.dict(
            os.environ,
            {
                "SECRET_KEY": "test-only-secret-key-with-more-than-32-bytes",
                "ALGORITHM": "HS256",
                "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
                "GROQ_API_KEY": "test-only",
            },
        )
        self.environment.start()
        from backend.app.core.config import get_settings

        get_settings.cache_clear()
        self.client = TestClient(app)

    async def _create_schema(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def _add_admin(self) -> None:
        from backend.app.core.security import hash_password

        async with self.session_factory() as session:
            session.add(
                User(
                    email="admin@example.edu",
                    full_name="EU Admin",
                    hashed_password=hash_password("strong-admin-pass-123"),
                    role=UserRole.ADMIN,
                )
            )
            await session.commit()

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()
        self.environment.stop()
        from backend.app.core.config import get_settings

        get_settings.cache_clear()
        asyncio.run(self.engine.dispose())
        self.temp_directory.cleanup()

    def register_student(self, student_id: str = "2026-0001") -> dict:
        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "student_id": student_id,
                "email": "Student@Example.edu",
                "full_name": "EU Student",
                "password": "strong-student-pass-123",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["role"], "student")
        return response.json()

    def login(
        self,
        identifier: str,
        password: str,
        login_type: str = "student",
    ) -> str:
        response = self.client.post(
            "/api/v1/auth/login",
            data={
                "username": identifier,
                "password": password,
                "login_type": login_type,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["token_type"], "bearer")
        return response.json()["access_token"]

    def test_registration_login_me_and_duplicate_email(self) -> None:
        user = self.register_student()
        self.assertNotIn("hashed_password", user)
        self.assertEqual(
            self.client.post(
                "/api/v1/auth/register",
                json={
                    "student_id": "2026-0002",
                    "email": "student@example.edu",
                    "full_name": "Another Student",
                    "password": "strong-student-pass-123",
                },
            ).status_code,
            409,
        )
        token = self.login("2026-0001", "strong-student-pass-123")
        me = self.client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["id"], user["id"])
        self.assertEqual(
            self.client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer invalid-token"},
            ).status_code,
            401,
        )
        expired_token = jwt.encode(
            {
                "sub": user["id"],
                "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            },
            "test-only-secret-key-with-more-than-32-bytes",
            algorithm="HS256",
        )
        self.assertEqual(
            self.client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {expired_token}"},
            ).status_code,
            401,
        )

    def test_registration_cannot_assign_admin_role(self) -> None:
        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "attacker@example.edu",
                "student_id": "2026-0003",
                "full_name": "Student",
                "password": "strong-student-pass-123",
                "role": "admin",
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_student_id_is_unique_and_student_cannot_login_with_email(self) -> None:
        self.register_student()
        duplicate = self.client.post(
            "/api/v1/auth/register",
            json={
                "student_id": "2026-0001",
                "email": "another@example.edu",
                "full_name": "Other Student",
                "password": "another-strong-pass-123",
            },
        )
        self.assertEqual(duplicate.status_code, 409, duplicate.text)
        wrong_identifier = self.client.post(
            "/api/v1/auth/login",
            data={
                "username": "student@example.edu",
                "password": "strong-student-pass-123",
            },
        )
        self.assertEqual(wrong_identifier.status_code, 401)

    def test_health_requires_migrated_auth_database(self) -> None:
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "ok")

    def test_chat_requires_login_logs_user_and_admin_route_is_guarded(self) -> None:
        self.assertEqual(
            self.client.post(
                "/api/v1/chat",
                json={"message": "Admission requirements?", "language": "en"},
            ).status_code,
            401,
        )
        student = self.register_student()
        student_token = self.login(
            "2026-0001", "strong-student-pass-123"
        )
        student_headers = {"Authorization": f"Bearer {student_token}"}
        self.assertEqual(self.client.get("/api/v1/admin/users").status_code, 401)
        self.assertEqual(
            self.client.get(
                "/api/v1/admin/users", headers=student_headers
            ).status_code,
            403,
        )

        with patch(
            "backend.app.main._run_rag",
            return_value={"answer": "Verified answer", "context": []},
        ):
            response = self.client.post(
                "/api/v1/chat",
                headers=student_headers,
                json={"message": "Admission requirements?", "language": "en"},
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["answer"], "Verified answer")

        async def count_user_chat_logs() -> int:
            async with self.session_factory() as session:
                return int(
                    await session.scalar(
                        select(func.count())
                        .select_from(ChatLog)
                        .where(ChatLog.user_id == UUID(student["id"]))
                    )
                    or 0
                )

        self.assertEqual(asyncio.run(count_user_chat_logs()), 1)

        asyncio.run(self._add_admin())
        self.assertEqual(
            self.client.post(
                "/api/v1/auth/login",
                data={
                    "username": "admin@example.edu",
                    "password": "strong-admin-pass-123",
                    "login_type": "student",
                },
            ).status_code,
            401,
        )
        admin_token = self.login(
            "admin@example.edu", "strong-admin-pass-123", "admin"
        )
        admin_response = self.client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(admin_response.status_code, 200, admin_response.text)
        self.assertEqual(admin_response.json()["total"], 2)
        self.assertEqual(
            {user["role"] for user in admin_response.json()["users"]},
            {"admin", "student"},
        )

    def test_chat_reports_groq_api_key_rejection(self) -> None:
        self.register_student()
        token = self.login("2026-0001", "strong-student-pass-123")
        request = Request("POST", "https://api.groq.com")
        error_response = Response(401, request=request)
        with patch(
            "backend.app.main._run_rag",
            side_effect=APIStatusError(
                "Invalid Groq API key", response=error_response, body=None
            ),
        ):
            response = self.client.post(
                "/api/v1/chat",
                headers={"Authorization": f"Bearer {token}"},
                json={"message": "Admission requirements?", "language": "en"},
            )

        self.assertEqual(response.status_code, 401, response.text)
        self.assertIn("Groq rejected the request", response.json()["detail"])
        self.assertIn("GROQ_API_KEY", response.json()["detail"])

    def test_admin_overview_upload_list_and_delete_documents(self) -> None:
        asyncio.run(self._add_admin())
        token = self.login("admin@example.edu", "strong-admin-pass-123", "admin")
        headers = {"Authorization": f"Bearer {token}"}
        from backend.app.api.v1.endpoints import admin

        temporary_root = Path(self.temp_directory.name)
        upload_directory = temporary_root / "data" / "raw" / "uploaded"
        with (
            patch.object(admin, "PROJECT_ROOT", temporary_root),
            patch.object(admin, "UPLOAD_DIRECTORY", upload_directory),
            patch.object(
                admin,
                "_run_reindex",
                return_value={"source_document_count": 1, "indexed_chunk_count": 3},
            ),
            patch.object(admin, "_count_indexed_chunks", return_value=3),
        ):
            overview = self.client.get(
                "/api/v1/admin/overview", headers=headers
            )
            self.assertEqual(overview.status_code, 200, overview.text)
            self.assertEqual(overview.json()["user_count"], 1)
            self.assertEqual(overview.json()["indexed_chunk_count"], 3)

            upload = self.client.post(
                "/api/v1/admin/documents",
                headers=headers,
                files={"file": ("policy.md", b"# Admission policy", "text/markdown")},
            )
            self.assertEqual(upload.status_code, 201, upload.text)
            self.assertTrue(upload.json()["managed"])
            self.assertTrue((upload_directory / "policy.md").is_file())

            listed = self.client.get("/api/v1/admin/documents", headers=headers)
            self.assertEqual(listed.status_code, 200, listed.text)
            self.assertEqual(listed.json()["total"], 1)

            deleted = self.client.delete(
                "/api/v1/admin/documents/policy.md", headers=headers
            )
            self.assertEqual(deleted.status_code, 204, deleted.text)
            self.assertFalse((upload_directory / "policy.md").exists())


if __name__ == "__main__":
    unittest.main()
