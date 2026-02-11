# راهنمای نصب کامل - Complete Installation Guide

## 📱 نصب روی Termux (اندروید)

### مرحله ۱: نصب Termux
1. از F-Droid Termux را نصب کنید:
   - [F-Droid Termux](https://f-droid.org/en/packages/com.termux/)
2. (اختیاری) Termux:Boot را برای اجرای خودکار نصب کنید

### مرحله ۲: اجرای اسکریپت نصب
```bash
# دانلود اسکریپت نصب
curl -O https://raw.githubusercontent.com/yourusername/telegram-reporter-pro/main/scripts/termux_setup.sh

# اجرای اسکریپت
bash termux_setup.sh