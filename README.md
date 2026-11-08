# JASSIM AI — Android + Cloud Dashboard

مشروع JASSIM AI يتكوّن من تطبيق Android، وخادم API ذاتي الاستضافة، ولوحة تحكم ويب عربية.

## المكونات
- `app/`: تطبيق Android الحالي. لم يتم استبداله أو حذف واجهته.
- `backend/server.py`: خادم Python خفيف مع SQLite، متوافق مع `POST /api/chat`.
- `dashboard/`: لوحة تحكم عربية RTL للمحادثة ومراقبة اتصال الخادم.
- `.github/workflows/android.yml`: اختبارات الخادم وبناء APK.
- `.github/workflows/pages.yml`: نشر لوحة التحكم على GitHub Pages.

## النشر
بعد تفعيل GitHub Pages على المستودع واختيار GitHub Actions كمصدر، ينشر workflow مجلد `dashboard` تلقائياً عند تحديثه.

## تشغيل API على Termux
```sh
pkg install python curl -y
mkdir -p ~/JASSIM_SERVER
cd ~/JASSIM_SERVER
curl -fL https://raw.githubusercontent.com/stevennpllk-crypto/-JASSIM-AI-Android/main/backend/server.py -o server.py
python server.py
```
افحص الخادم من جلسة ثانية:
```sh
curl http://127.0.0.1:8787/health
```

الخادم يستمع إلى `127.0.0.1` افتراضياً ولا ينبغي كشفه للإنترنت مباشرة. دعم CORS موجود للوحة الويب، لكن قبل أي نشر عام يجب إضافة مصادقة، وتحديد المعدل، وHTTPS، وتقييد مصدر CORS إلى نطاق لوحة التحكم.

## حدود واضحة
وجود لوحة ويب لا يعني وجود GPU أو استضافة دائمة. الهاتف يمكنه تشغيل API والتخزين، أما نموذج كبير فيحتاج جهازاً منفصلاً بموارد مناسبة. حالة الاتصال في الواجهة تعتمد على رد الخادم الحقيقي.
