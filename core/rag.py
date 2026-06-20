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

        # تحديث: رجعنا لـ Gemini Embeddings (API-based) بدل HuggingFace
        # المحلي، لأن مشكلة 403 PERMISSION_DENIED اتحلت ومعانا GOOGLE_API_KEY
        # شغال دلوقتي. السبب الرئيسي للرجوع: التطبيق منشور على Streamlit
        # Community Cloud بحد 1GB RAM، وموديل HuggingFace المحلي (~420MB
        # يتحمّل في ذاكرة العملية نفسها) خطر فعلي على استقرار السيرفر تحت
        # هذا القيد - الـ API-based embeddings لا تستهلك أي RAM محلي خالص.
        #
        # ملحوظة مهمة عن اسم الموديل: استخدام "gemini-embedding-001" بدون
        # "models/" prefix هو الصحيح هنا تحديداً (Gemini Developer API /
        # Google AI Studio، use_vertexai=False) - مكتوب بالتفصيل في
        # CHANGES.txt القسم (1)، وكان سبب فشل سابق برسالة "model not found"
        # لما كان الاسم مكتوب بالـ prefix.
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
            # تحقق دفاعي: لو قاعدة Chroma فاضية (مثلاً لأن build_vector_db.py
            # لم يُشغَّل بعد، أو شُغِّل قبل حذف vector_db القديمة)، الوكيل
            # سيحصل على نص فاضي من كل بحث RAG بصمت تام، ويبدو كأن "لا توجد
            # معلومات" عن كل شيء بينما المشكلة فعلياً هي قاعدة فاضية فقط.
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

        # ملاحظة تحسين توكنز: كانت k=8 يعني حتى 8 قطع × ~700 حرف تقريباً تُحشر
        # في الـ prompt لكل بحث - وهي السبب الأكبر في قفزة التوكنز بين الـ
        # request الأول (1,506) والثاني (2,608) في اللوج. 4 قطع كافية عملياً
        # لتغطية أي سياسة أو سعر أو pitch محدد، وتقلل هذا الجزء للنصف.
        results = self.db.similarity_search(
            question,
            k=4
        )


        context="\n\n".join(
            r.page_content
            for r in results
        )


        return context