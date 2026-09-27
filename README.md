# Telegram Kino Qidiruv Boti

## O'rnatish

1. Python 3.10+ o'rnatilgan bo'lishi kerak.
2. Kutubxonalarni o'rnating:
   ```
   pip install -r requirements.txt
   ```
3. Muhit o'zgaruvchilarini sozlang (yoki to'g'ridan-to'g'ri `bot.py` faylida o'zgartiring):
   - `BOT_TOKEN` — BotFather'dan olingan token
   - `ADMIN_IDS` — admin(lar)ning Telegram user ID raqami(lari), vergul bilan ajratilgan (masalan: `123456789,987654321`)
   - `REQUIRED_CHANNEL` — (ixtiyoriy) majburiy obuna kanali username'i, masalan `@mening_kanalim`. Bo'sh qoldirsangiz, bu tekshiruv ishlamaydi.

   Linux/macOS'da:
   ```
   export BOT_TOKEN="123456:ABC..."
   export ADMIN_IDS="123456789"
   ```
   Windows PowerShell'da:
   ```
   $env:BOT_TOKEN="123456:ABC..."
   $env:ADMIN_IDS="123456789"
   ```

4. Botni ishga tushiring:
   ```
   python bot.py
   ```

## Foydalanish

### Oddiy foydalanuvchi
- Botga `/start` yozadi.
- Kino kodini (masalan `101`) yuboradi — bot mos videoni topib yuboradi.

### Admin
- **Kino qo'shish:** Botga video faylni yuboring, video captioniga kino raqamini yozing (masalan caption: `101`). Bot avtomatik bazaga saqlaydi.
- **O'chirish:** `/delete 101`
- **Ro'yxat:** `/list`
- **Statistika:** `/stats`

## Muhim eslatma — token xavfsizligi

Bot tokenini hech qachon ochiq kodga yoki chatlarga yozmang. Uni faqat muhit o'zgaruvchisi (`.env` yoki server sozlamalari) orqali bering. Agar tokeningiz kimgadir oshkor bo'lgan bo'lsa, BotFaher'da `/revoke` qilib, yangisini oling.

## Kengaytirish g'oyalari
- Kino nomi bo'yicha qidiruv (hozircha faqat raqam bo'yicha)
- Inline qidiruv
- Kategoriyalar/janrlar bo'yicha filtrlash
- Admin panelni web interfeys orqali boshqarish
