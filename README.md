# ทุเรียนดี — ผู้ช่วยชาวสวนทุเรียน (REST API ครบ 10 ข้อ)

โปรเจกต์ชุดนี้รวม Frontend + FastAPI + PostgreSQL + Docker Compose และแก้ REST API ตามโจทย์ Authentication / User Management ให้ครบทั้ง 10 endpoint

## 10 Endpoint ตามโจทย์

### 1) Authentication
- [x] `POST /register` — สมัครสมาชิก
- [x] `POST /login` — เข้าสู่ระบบและรับ JWT
- [x] `POST /logout` — ออกจากระบบและ revoke token
- [x] `POST /change-password` — เปลี่ยนรหัสผ่าน

### 2) User Management
- [x] `GET /me` — ดึงข้อมูลตัวเอง
- [x] `GET /users/{id}` — ดึงข้อมูลผู้ใช้ตาม ID
- [x] `GET /users` — ดึงผู้ใช้ทั้งหมดแบบ pagination
- [x] `PUT /users/{id}` — แก้ไข username/email ของบัญชีตัวเอง
- [x] `DELETE /users/{id}` — ลบบัญชีตัวเอง
- [x] `GET /check-username/{name}` — ตรวจสอบ username ว่างหรือไม่

## เพิ่มเติม

- Community API: posts + comments
- `/diagnose`: endpoint รับรูป JPG/PNG/WEBP สำหรับ workflow AI demo
- Swagger UI: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/api/health`

## แก้ปัญหา phpMyAdmin #1046 No database selected

ไฟล์ `init.sql` ถูกทำเป็น **MySQL/phpMyAdmin version** ใหม่และมี:

```sql
CREATE DATABASE IF NOT EXISTS durian_db;
USE durian_db;
```

ดังนั้นสามารถเข้า phpMyAdmin > Import > เลือก `init.sql` ได้โดยไม่ต้องเลือกฐานข้อมูลล่วงหน้า

> หมายเหตุ: Docker Compose ของโปรเจกต์นี้ใช้ PostgreSQL ดังนั้น Docker จะใช้ `init-postgres.sql` ส่วน `init.sql` มีไว้สำหรับการทดสอบ/นำเข้าใน MySQL/phpMyAdmin ตามภาพที่ส่งมา

## วิธีรัน Docker

1. คัดลอก `.env.example` เป็น `.env`
2. เปลี่ยน `SECRET_KEY`
3. รัน `docker compose up --build`
4. เปิด `http://localhost:8000`
5. เปิด Swagger ที่ `http://localhost:8000/docs`
6. เปิด pgAdmin ที่ `http://localhost:8080`

## การทดสอบ 10 API แบบง่าย

1. `POST /register`
2. `POST /login` และคัดลอก `access_token`
3. ใน Swagger กด **Authorize** แล้วใส่ `Bearer <token>`
4. ทดสอบ `GET /me`
5. ทดสอบ `GET /users?page=1&page_size=10`
6. ทดสอบ `GET /users/{id}`
7. ทดสอบ `GET /check-username/{name}`
8. ทดสอบ `PUT /users/{id}`
9. ทดสอบ `POST /change-password`
10. ทดสอบ `POST /logout`
11. สำหรับ `DELETE /users/{id}` ให้ใช้หลังจากทดสอบ endpoint อื่น ๆ เพราะจะลบบัญชีจริง

## Logout

ระบบใช้ JWT พร้อม `jti` และตาราง `revoked_tokens` เพื่อให้ `/logout` ยกเลิก token ทางฝั่ง server ได้จริง ไม่ใช่แค่ลบ token จาก browser
