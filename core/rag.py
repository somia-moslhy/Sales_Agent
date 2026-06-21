from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import os



class KayfaRAG:


    def __init__(self, documents):

        self.documents = documents

        

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,
            chunk_overlap=150,
            separators=["\n\n", "\n", "|", " ", ""]
        )


        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="gemini-embedding-001"
        )



    def create_database(self):

        chunks=[]


        for doc in self.documents:

            parts = self.splitter.split_text(
                doc["content"]
            )


            chunks.extend(parts)



        db = Chroma.from_texts(
            texts=chunks,
            embedding=self.embeddings,
            persist_directory="vector_db"
        )


        self.db = db


        return db

    def load_database(self):
            self.db = Chroma(
                persist_directory="vector_db",
                embedding_function=self.embeddings
            )
       
            try:
                count = self.db._collection.count()
            except Exception:
                count = None
            if not count:
                print(
                    "⚠️  تحذير: vector_db فاضية أو غير موجودة! "
                    "شغّل أولاً: python build_vector_db.py "
                    "قبل تشغيل streamlit run app.py، وإلا سيفشل كل بحث RAG بصمت."
                )
            return self.db


    def search(self, question):

   
        results = self.db.similarity_search(
            question,
            k=4
        )


        context="\n\n".join(
            r.page_content
            for r in results
        )


        return context