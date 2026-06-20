"""
يبني قاعدة بيانات Chroma (vector_db) من ملفات data/*.md من الصفر.
شغّل السكريبت ده مرة واحدة قبل أول تشغيل للتطبيق، وأي مرة تعدّل فيها
ملفات data/ أو تغيّر اسم/نوع موديل الـ embeddings في core/rag.py.

الاستخدام:
    python build_vector_db.py
"""
from dotenv import load_dotenv
load_dotenv()

from core.loader import DataLoader
from core.rag import KayfaRAG


def main():
    print("📂 تحميل ملفات المعرفة (data/*.md) ...")
    loader = DataLoader()
    docs = loader.load_text()

    if not docs:
        print("⚠️  لم يتم العثور على أي ملفات .md داخل مجلد data/. تأكد من المسار.")
        return

    print(f"✅ تم تحميل {len(docs)} ملف نصي.")
    print("🧠 إنشاء قاعدة المتجهات (هذا يستخدم Gemini Embeddings API ويستهلك تكلفة بسيطة) ...")

    rag = KayfaRAG(docs)
    rag.create_database()

    print("🎉 تم بناء vector_db بنجاح! التطبيق جاهز للتشغيل الآن (streamlit run app.py).")


if __name__ == "__main__":
    main()
