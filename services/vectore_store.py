
import chromadb
from pathlib import Path


class VectorStore:
    def __init__(self):
        # Store the database inside the project directory.
        db_path = Path("chroma_db")
        db_path.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(db_path)
        )

        # Create or reuse our document collection.
        self.collection = self.client.get_or_create_collection(
            name="agenthire_documents",
            metadata={"hnsw:space": "cosine"}
        )

    def add_text(
        self,
        document_id: str,
        text: str,
        source: str,
        application_id: str
    ) -> int:
        """
        Split text into chunks and store them in ChromaDB.
        """

        if not text or not text.strip():
            raise ValueError("Text cannot be empty.")

        if not document_id.strip() or not application_id.strip():
            raise ValueError(
                "Document ID and application ID are required."
            )

        # Simple paragraph-aware chunking.
        paragraphs = [
            paragraph.strip()
            for paragraph in text.splitlines()
            if paragraph.strip()
        ]

        chunks = []
        current_chunk = ""

        for paragraph in paragraphs:
            # Split unusually long paragraphs into smaller pieces.
            if len(paragraph) > 1000:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""

                for start in range(0, len(paragraph), 1000):
                    chunks.append(paragraph[start:start + 1000])
                continue

            if len(current_chunk) + len(paragraph) > 1000:
                chunks.append(current_chunk)
                current_chunk = paragraph
            else:
                current_chunk = (
                    current_chunk + "\n" + paragraph
                    if current_chunk else paragraph
                )

        if current_chunk:
            chunks.append(current_chunk)

        if not chunks:
            raise ValueError("No text chunks could be created.")

        ids = [
            f"{document_id}_chunk_{index}"
            for index in range(len(chunks))
        ]

        metadatas = [
            {
                "document_id": document_id,
                "application_id": application_id,
                "source": source,
                "chunk_index": index
            }
            for index in range(len(chunks))
        ]

        # ChromaDB generates embeddings using its configured
        # embedding function.
        self.collection.upsert(
            ids=ids,
            documents=chunks,
            metadatas=metadatas
        )

        return len(chunks)

    def search_similar(
        self,
        query: str,
        application_id: str,
        n_results: int = 3
    ) -> list:
        """
        Retrieve relevant text chunks for one application.
        """

        if not query or not query.strip():
            raise ValueError("Search query cannot be empty.")

        if not application_id.strip():
            raise ValueError("Application ID is required.")

        if n_results < 1:
            raise ValueError("n_results must be at least 1.")

        # Prevent one candidate's documents from appearing
        # in another candidate's search results.
        result_count = min(
            n_results,
            self.collection.count()
        )

        if result_count == 0:
            return []

        results = self.collection.query(
            query_texts=[query],
            n_results=result_count,
            where={"application_id": application_id},
            include=["documents", "metadatas", "distances"]
        )

        matches = []

        for index, document in enumerate(results["documents"][0]):
            matches.append({
                "text": document,
                "metadata": results["metadatas"][0][index],
                "distance": results["distances"][0][index]
            })

        return matches

    def delete_application(self, application_id: str) -> None:
        """
        Delete all stored chunks belonging to an application.
        """

        if not application_id.strip():
            raise ValueError("Application ID is required.")

        self.collection.delete(
            where={"application_id": application_id}
        )
