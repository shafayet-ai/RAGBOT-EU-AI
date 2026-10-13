import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.documents import Document

from root import ingest


class IngestionPipelineTests(unittest.TestCase):
    def test_reindex_updates_changed_files_and_removes_deleted_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_directory = Path(temporary_directory)
            documents_directory = project_directory / "university_docs"
            scraped_directory = project_directory / "data" / "raw" / "scraped"
            uploaded_directory = project_directory / "data" / "raw" / "uploaded"
            documents_directory.mkdir(parents=True)
            scraped_directory.mkdir(parents=True)
            uploaded_directory.mkdir(parents=True)
            document_path = documents_directory / "admission.md"
            document_path.write_text(
                '---\nDocument Type: "Admission"\nDepartment: "General"\n'
                "---\n\n"
                + "admission " * 220,
                encoding="utf-8",
            )

            class FakeEmbeddings:
                def __init__(
                    self,
                    model_name: str,
                    model_kwargs: dict[str, str],
                    encode_kwargs: dict[str, bool],
                ) -> None:
                    self.model_name = model_name

            class FakeVectorStore:
                stores: dict[str, dict[str, Document]] = {}

                def __init__(
                    self,
                    *,
                    persist_directory: str,
                    embedding_function: FakeEmbeddings,
                    collection_name: str,
                ) -> None:
                    self.documents = self.stores.setdefault(persist_directory, {})

                def get(
                    self,
                    *,
                    where: dict[str, str] | None = None,
                    include: list[str],
                ) -> dict[str, list]:
                    found = [
                        (document_id, document)
                        for document_id, document in self.documents.items()
                        if where is None
                        or document.metadata.get("source") == where["source"]
                    ]
                    result = {"ids": [document_id for document_id, _ in found]}
                    if "metadatas" in include:
                        result["metadatas"] = [
                            document.metadata for _, document in found
                        ]
                    return result

                def add_documents(
                    self, *, documents: list[Document], ids: list[str]
                ) -> None:
                    self.documents.update(zip(ids, documents, strict=True))

                def update_documents(
                    self, *, ids: list[str], documents: list[Document]
                ) -> None:
                    self.documents.update(zip(ids, documents, strict=True))

                def delete(self, *, ids: list[str]) -> None:
                    for document_id in ids:
                        self.documents.pop(document_id, None)

            with (
                patch.object(ingest, "PROJECT_DIR", project_directory),
                patch.object(ingest, "DOCUMENTS_DIR", documents_directory),
                patch.object(ingest, "SCRAPED_DOCUMENTS_DIR", scraped_directory),
                patch.object(ingest, "UPLOADED_DOCUMENTS_DIR", uploaded_directory),
                patch.object(ingest, "HuggingFaceEmbeddings", FakeEmbeddings),
                patch.object(ingest, "Chroma", FakeVectorStore),
            ):
                first_index = ingest.process_documents()
                store = FakeVectorStore.stores[
                    str(project_directory / "chroma_db_huggingface")
                ]
                first_ids = set(store)
                self.assertGreater(first_index["indexed_chunk_count"], 1)
                self.assertTrue(
                    all(
                        document.metadata["document_type"] == "admission"
                        and document.metadata["department"] == "general"
                        for document in store.values()
                    )
                )

                document_path.write_text("updated admission information", encoding="utf-8")
                second_index = ingest.process_documents()
                second_ids = set(store)
                self.assertEqual(second_index["indexed_chunk_count"], 1)
                self.assertNotEqual(first_ids, second_ids)
                self.assertEqual(len(store), 1)

                document_path.unlink()
                empty_index = ingest.process_documents()
                self.assertEqual(empty_index["source_document_count"], 0)
                self.assertEqual(empty_index["indexed_chunk_count"], 0)
                self.assertEqual(store, {})


if __name__ == "__main__":
    unittest.main()
