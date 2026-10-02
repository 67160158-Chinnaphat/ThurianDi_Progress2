from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
import os
import uuid

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, text
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://myuser:mypassword@127.0.0.1:5432/mydb",
)
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()

app = FastAPI(title="Durian Farmer Assistant API", version="4.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in CORS_ORIGINS.split(",")] if CORS_ORIGINS != "*" else ["*"],
    allow_credentials=CORS_ORIGINS != "*",
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Database Models ====================
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    # role: "user" (ผู้ใช้ทั่วไป), "seller" (ผู้ขาย), "admin" (ผู้ดูแลระบบ)
    role = Column(String(20), default="user", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="author", cascade="all, delete-orphan")
    shop = relationship("Shop", back_populates="seller", uselist=False, cascade="all, delete-orphan")


class Shop(Base):
    __tablename__ = "shops"
    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    address = Column(String(500), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    seller = relationship("User", back_populates="shop")
    products = relationship("Product", back_populates="shop", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, ForeignKey("shops.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    unit = Column(String(50), default="ชิ้น", nullable=False)
    price = Column(Float, default=0, nullable=False)
    stock_quantity = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    shop = relationship("Shop", back_populates="products")
    reviews = relationship("ProductReview", back_populates="product", cascade="all, delete-orphan")


class ProductReview(Base):
    __tablename__ = "product_reviews"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    product = relationship("Product", back_populates="reviews")
    author = relationship("User")


class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(50), default="general", index=True)
    image_url = Column(String(500), nullable=True)
    rating = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    author = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")


class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    post = relationship("Post", back_populates="comments")
    author = relationship("User", back_populates="comments")


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"
    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String(64), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, default=datetime.utcnow, nullable=False)


Base.metadata.create_all(bind=engine)

# Auto-migration: ถ้าฐานข้อมูลเดิมถูกสร้างไว้ก่อนมีคอลัมน์ role ให้เติมให้อัตโนมัติ
# (create_all ด้านบนจะสร้างตารางใหม่ที่ยังไม่มีให้ แต่จะไม่แก้ตารางเก่าที่มีอยู่แล้ว)
with engine.begin() as conn:
    conn.execute(
        text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user'"
        )
    )


# ==================== Schemas ====================
class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(min_length=5, max_length=100)
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6, max_length=128)


class UserUpdate(BaseModel):
    username: Optional[str] = Field(default=None, min_length=3, max_length=50)
    email: Optional[str] = Field(default=None, min_length=5, max_length=100)


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SellerCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(min_length=5, max_length=100)
    password: str = Field(min_length=6, max_length=128)
    shop_name: str = Field(min_length=1, max_length=200)


class RoleUpdate(BaseModel):
    role: str = Field(description="user, seller หรือ admin")


class ShopUpsert(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: Optional[str] = Field(default=None, max_length=500)
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ShopResponse(BaseModel):
    id: int
    seller_id: int
    seller_username: str
    name: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: datetime


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    unit: str = Field(default="ชิ้น", max_length=50)
    price: float = Field(ge=0)
    stock_quantity: int = Field(ge=0)


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    unit: Optional[str] = Field(default=None, max_length=50)
    price: Optional[float] = Field(default=None, ge=0)
    stock_quantity: Optional[int] = Field(default=None, ge=0)


class ProductResponse(BaseModel):
    id: int
    shop_id: int
    shop_name: str
    name: str
    unit: str
    price: float
    stock_quantity: int
    created_at: datetime
    updated_at: datetime
    avg_rating: Optional[float] = None
    review_count: int = 0


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=2000)


class ReviewResponse(BaseModel):
    id: int
    product_id: int
    user_id: int
    username: str
    rating: int
    comment: Optional[str] = None
    created_at: datetime


class UserListResponse(BaseModel):
    items: List[UserResponse]
    page: int
    page_size: int
    total: int
    pages: int


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class MessageResponse(BaseModel):
    message: str


class UsernameCheckResponse(BaseModel):
    username: str
    available: bool


class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10000)
    category: str = "general"
    image_url: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)


class PostResponse(BaseModel):
    id: int
    user_id: int
    username: str
    title: str
    content: str
    category: str
    image_url: Optional[str] = None
    rating: Optional[int] = None
    created_at: datetime
    comment_count: int = 0


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class CommentResponse(BaseModel):
    id: int
    post_id: int
    user_id: int
    username: str
    content: str
    created_at: datetime


# ==================== Helpers ====================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: int, username: str, role: str) -> str:
    now = datetime.utcnow()
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_token_payload(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=401,
        detail="กรุณาเข้าสู่ระบบก่อนใช้งานส่วนนี้",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        jti = payload.get("jti")
        exp = payload.get("exp")
        if not user_id or not jti or not exp:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc

    revoked = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
    if revoked:
        raise credentials_exception
    return payload


def get_current_user(
    payload=Depends(get_current_token_payload), db: Session = Depends(get_db)
) -> User:
    user = db.query(User).filter(User.id == payload["user_id"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="บัญชีนี้ไม่สามารถใช้งานได้")
    return user


def ensure_self(user_id: int, current_user: User):
    # admin จัดการบัญชีใครก็ได้ ส่วนคนอื่นจัดการได้แค่ของตัวเอง
    if user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="คุณสามารถจัดการข้อมูลของบัญชีตัวเองเท่านั้น")


def require_role(*allowed_roles: str):
    """Dependency factory: จำกัด endpoint ให้เฉพาะ role ที่กำหนด (admin ผ่านได้เสมอ)"""

    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != "admin" and current_user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="คุณไม่มีสิทธิ์ใช้งานส่วนนี้")
        return current_user

    return checker


def get_own_shop_or_404(current_user: User, db: Session) -> Shop:
    shop = db.query(Shop).filter(Shop.seller_id == current_user.id).first()
    if not shop:
        raise HTTPException(status_code=404, detail="คุณยังไม่มีร้านค้า กรุณาให้ผู้ดูแลระบบสร้างบัญชีผู้ขายให้ก่อน")
    return shop


def to_shop_response(shop: Shop) -> ShopResponse:
    return ShopResponse(
        id=shop.id,
        seller_id=shop.seller_id,
        seller_username=shop.seller.username,
        name=shop.name,
        address=shop.address,
        latitude=shop.latitude,
        longitude=shop.longitude,
        created_at=shop.created_at,
    )


def to_product_response(product: Product) -> ProductResponse:
    ratings = [r.rating for r in product.reviews]
    return ProductResponse(
        id=product.id,
        shop_id=product.shop_id,
        shop_name=product.shop.name,
        name=product.name,
        unit=product.unit,
        price=product.price,
        stock_quantity=product.stock_quantity,
        created_at=product.created_at,
        updated_at=product.updated_at,
        avg_rating=round(sum(ratings) / len(ratings), 2) if ratings else None,
        review_count=len(ratings),
    )


def to_review_response(review: ProductReview) -> ReviewResponse:
    return ReviewResponse(
        id=review.id,
        product_id=review.product_id,
        user_id=review.user_id,
        username=review.author.username,
        rating=review.rating,
        comment=review.comment,
        created_at=review.created_at,
    )


def to_post_response(post: Post) -> PostResponse:
    return PostResponse(
        id=post.id,
        user_id=post.user_id,
        username=post.author.username,
        title=post.title,
        content=post.content,
        category=post.category,
        image_url=post.image_url,
        rating=post.rating,
        created_at=post.created_at,
        comment_count=len(post.comments),
    )


def to_comment_response(comment: Comment) -> CommentResponse:
    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        user_id=comment.user_id,
        username=comment.author.username,
        content=comment.content,
        created_at=comment.created_at,
    )


# ==================== System ====================
@app.get("/api/health")
def health():
    return {"status": "ok", "service": "durian-assistant", "version": app.version}


def _static_handler(filename: str, media_type: str):
    def handler():
        return FileResponse(BASE_DIR / filename, media_type=media_type)
    return handler


# หน้าเว็บ: "/" คือหน้า login ส่วนแต่ละหน้าเช็กสิทธิ์เองด้วย requireAuth() ใน common.js
STATIC_FILES = {
    "/": ("login.html", "text/html"),
    "/login.html": ("login.html", "text/html"),
    "/user.html": ("user.html", "text/html"),
    "/seller.html": ("seller.html", "text/html"),
    "/admin.html": ("admin.html", "text/html"),
    "/common.js": ("common.js", "text/javascript"),
    "/app.js": ("app.js", "text/javascript"),
    "/style.css": ("style.css", "text/css"),
}
for _route, (_file, _media) in STATIC_FILES.items():
    app.add_api_route(_route, _static_handler(_file, _media), methods=["GET"], include_in_schema=False)


# ==================== 1. Authentication ====================
@app.post("/register", response_model=UserResponse, tags=["Authentication"])
def register(user: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="ชื่อผู้ใช้นี้ถูกใช้งานแล้ว")
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="อีเมลนี้ถูกใช้งานแล้ว")

    new_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hash_password(user.password),
        role="user",  # สมัครผ่านหน้าเว็บได้แค่ role user เท่านั้น ห้ามรับค่า role จาก client
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.post("/login", response_model=TokenResponse, tags=["Authentication"])
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    if not db_user.is_active:
        raise HTTPException(status_code=403, detail="บัญชีนี้ถูกปิดใช้งาน")
    token = create_access_token(db_user.id, db_user.username, db_user.role)
    return {"access_token": token, "token_type": "bearer", "user": db_user}


@app.post("/logout", response_model=MessageResponse, tags=["Authentication"])
def logout(
    payload=Depends(get_current_token_payload), db: Session = Depends(get_db)
):
    jti = payload["jti"]
    existing = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
    if not existing:
        exp_dt = datetime.utcfromtimestamp(payload["exp"])
        db.add(RevokedToken(jti=jti, expires_at=exp_dt))
        db.commit()
    return {"message": "ออกจากระบบเรียบร้อยแล้ว"}


@app.post("/change-password", response_model=MessageResponse, tags=["Authentication"])
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="รหัสผ่านปัจจุบันไม่ถูกต้อง")
    if data.current_password == data.new_password:
        raise HTTPException(status_code=400, detail="รหัสผ่านใหม่ต้องแตกต่างจากรหัสผ่านเดิม")
    current_user.hashed_password = hash_password(data.new_password)
    db.commit()
    return {"message": "เปลี่ยนรหัสผ่านเรียบร้อยแล้ว กรุณาเข้าสู่ระบบใหม่"}


# ==================== 2. User Management ====================
@app.get("/me", response_model=UserResponse, tags=["User Management"])
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@app.get("/users", response_model=UserListResponse, tags=["User Management"])
def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    q: Optional[str] = Query(default=None, description="ค้นหา username/email"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    if q:
        pattern = f"%{q}%"
        query = query.filter((User.username.ilike(pattern)) | (User.email.ilike(pattern)))
    total = query.count()
    users = (
        query.order_by(User.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    pages = (total + page_size - 1) // page_size if total else 0
    return {
        "items": users,
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": pages,
    }


@app.get("/users/{user_id}", dependencies=[Depends(get_current_user)], response_model=UserResponse, tags=["User Management"])
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้")
    return user


@app.put("/users/{user_id}", response_model=UserResponse, tags=["User Management"])
def update_user(
    user_id: int,
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_self(user_id, current_user)

    if data.username and data.username != current_user.username:
        if db.query(User).filter(User.username == data.username, User.id != user_id).first():
            raise HTTPException(status_code=400, detail="ชื่อผู้ใช้นี้ถูกใช้งานแล้ว")
        current_user.username = data.username

    if data.email and data.email != current_user.email:
        if db.query(User).filter(User.email == data.email, User.id != user_id).first():
            raise HTTPException(status_code=400, detail="อีเมลนี้ถูกใช้งานแล้ว")
        current_user.email = data.email

    db.commit()
    db.refresh(current_user)
    return current_user


@app.delete("/users/{user_id}", response_model=MessageResponse, tags=["User Management"])
def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_self(user_id, current_user)
    db.delete(current_user)
    db.commit()
    return {"message": "ลบบัญชีเรียบร้อยแล้ว"}


@app.get("/check-username/{name}", response_model=UsernameCheckResponse, tags=["User Management"])
def check_username(name: str, db: Session = Depends(get_db)):
    if not 3 <= len(name) <= 50:
        raise HTTPException(status_code=422, detail="username ต้องมีความยาว 3-50 ตัวอักษร")
    exists = db.query(User).filter(User.username == name).first() is not None
    return {"username": name, "available": not exists}


# ==================== 3. Admin: จัดการผู้ขาย/สิทธิ์ ====================
@app.post("/admin/sellers", response_model=UserResponse, tags=["Admin"])
def create_seller(
    data: SellerCreate,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Admin เท่านั้นที่สร้างบัญชีผู้ขายได้ (ผู้ขายลงทะเบียนหน้าเว็บเองไม่ได้)"""
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="ชื่อผู้ใช้นี้ถูกใช้งานแล้ว")
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="อีเมลนี้ถูกใช้งานแล้ว")

    new_seller = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        role="seller",
    )
    db.add(new_seller)
    db.flush()  # ให้ได้ new_seller.id ก่อน commit

    shop = Shop(seller_id=new_seller.id, name=data.shop_name)
    db.add(shop)
    db.commit()
    db.refresh(new_seller)
    return new_seller


@app.patch("/admin/users/{user_id}/role", response_model=UserResponse, tags=["Admin"])
def update_user_role(
    user_id: int,
    data: RoleUpdate,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    if data.role not in ("user", "seller", "admin"):
        raise HTTPException(status_code=422, detail="role ต้องเป็น user, seller หรือ admin เท่านั้น")
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="ไม่สามารถเปลี่ยนสิทธิ์ของบัญชีตัวเองได้")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้")
    target.role = data.role
    db.commit()
    db.refresh(target)
    return target


@app.get("/admin/stats", tags=["Admin"])
def admin_stats(current_user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """ภาพรวมระบบสำหรับหน้า Admin"""
    return {
        "users": db.query(User).count(),
        "sellers": db.query(User).filter(User.role == "seller").count(),
        "admins": db.query(User).filter(User.role == "admin").count(),
        "shops": db.query(Shop).count(),
        "products": db.query(Product).count(),
    }


# ==================== 4. ร้านค้า (Shop) ====================
@app.get("/shops", dependencies=[Depends(get_current_user)], response_model=List[ShopResponse], tags=["Shops"])
def list_shops(db: Session = Depends(get_db)):
    """สาธารณะ: ใช้แสดงหมุดร้านค้าบนแผนที่ให้ผู้ใช้ทั่วไปดู"""
    shops = db.query(Shop).order_by(Shop.id.asc()).all()
    return [to_shop_response(s) for s in shops]


@app.get("/shops/mine", response_model=ShopResponse, tags=["Shops"])
def get_my_shop(
    current_user: User = Depends(require_role("seller")),
    db: Session = Depends(get_db),
):
    shop = get_own_shop_or_404(current_user, db)
    return to_shop_response(shop)


@app.put("/shops/mine", response_model=ShopResponse, tags=["Shops"])
def update_my_shop(
    data: ShopUpsert,
    current_user: User = Depends(require_role("seller")),
    db: Session = Depends(get_db),
):
    """ผู้ขายปักหมุดร้าน/แก้ไขชื่อร้านของตัวเอง"""
    shop = get_own_shop_or_404(current_user, db)
    shop.name = data.name
    shop.address = data.address
    shop.latitude = data.latitude
    shop.longitude = data.longitude
    db.commit()
    db.refresh(shop)
    return to_shop_response(shop)


# ==================== 5. สินค้าในคลัง (Products) ====================
@app.get("/products", dependencies=[Depends(get_current_user)], response_model=List[ProductResponse], tags=["Products"])
def list_products(
    shop_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    """สาธารณะ: ผู้ใช้ทั่วไปดูสินค้าทั้งหมดได้"""
    query = db.query(Product)
    if shop_id:
        query = query.filter(Product.shop_id == shop_id)
    return [to_product_response(p) for p in query.order_by(Product.id.asc()).all()]


@app.get("/products/mine", response_model=List[ProductResponse], tags=["Products"])
def list_my_products(
    current_user: User = Depends(require_role("seller")),
    db: Session = Depends(get_db),
):
    shop = get_own_shop_or_404(current_user, db)
    return [to_product_response(p) for p in shop.products]


@app.post("/products", response_model=ProductResponse, tags=["Products"])
def create_product(
    data: ProductCreate,
    current_user: User = Depends(require_role("seller")),
    db: Session = Depends(get_db),
):
    shop = get_own_shop_or_404(current_user, db)
    product = Product(shop_id=shop.id, **data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return to_product_response(product)


@app.put("/products/{product_id}", response_model=ProductResponse, tags=["Products"])
def update_product(
    product_id: int,
    data: ProductUpdate,
    current_user: User = Depends(require_role("seller")),
    db: Session = Depends(get_db),
):
    """อัปเดตสต๊อก/ราคาสินค้า: เจ้าของร้านเท่านั้น (admin ผ่านได้เสมอ)"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="ไม่พบสินค้า")
    if current_user.role != "admin" and product.shop.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="คุณจัดการได้แค่สินค้าในร้านของตัวเอง")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return to_product_response(product)


@app.delete("/products/{product_id}", response_model=MessageResponse, tags=["Products"])
def delete_product(
    product_id: int,
    current_user: User = Depends(require_role("seller")),
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="ไม่พบสินค้า")
    if current_user.role != "admin" and product.shop.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="คุณจัดการได้แค่สินค้าในร้านของตัวเอง")
    db.delete(product)
    db.commit()
    return {"message": "ลบสินค้าแล้ว"}


# ==================== 6. รีวิวสินค้า ====================
@app.get("/products/{product_id}/reviews", dependencies=[Depends(get_current_user)], response_model=List[ReviewResponse], tags=["Products"])
def list_product_reviews(product_id: int, db: Session = Depends(get_db)):
    """สาธารณะ: ทั้งผู้ใช้ทั่วไปและผู้ขายเช็ครีวิวสินค้าได้"""
    if not db.query(Product).filter(Product.id == product_id).first():
        raise HTTPException(status_code=404, detail="ไม่พบสินค้า")
    reviews = (
        db.query(ProductReview)
        .filter(ProductReview.product_id == product_id)
        .order_by(ProductReview.created_at.desc())
        .all()
    )
    return [to_review_response(r) for r in reviews]


@app.post("/products/{product_id}/reviews", response_model=ReviewResponse, tags=["Products"])
def create_product_review(
    product_id: int,
    data: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """ผู้ใช้ที่ล็อกอินแล้ว (role ใดก็ได้) ให้รีวิวสินค้าได้"""
    if not db.query(Product).filter(Product.id == product_id).first():
        raise HTTPException(status_code=404, detail="ไม่พบสินค้า")
    review = ProductReview(product_id=product_id, user_id=current_user.id, **data.model_dump())
    db.add(review)
    db.commit()
    db.refresh(review)
    return to_review_response(review)


# ==================== Community API ====================
@app.get("/posts", dependencies=[Depends(get_current_user)], response_model=List[PostResponse], tags=["Community"])
def list_posts(
    q: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Post)
    if category and category != "all":
        query = query.filter(Post.category == category)
    if q:
        pattern = f"%{q}%"
        query = query.filter((Post.title.ilike(pattern)) | (Post.content.ilike(pattern)))
    posts = query.order_by(Post.created_at.desc()).offset(skip).limit(limit).all()
    return [to_post_response(p) for p in posts]


@app.post("/posts", response_model=PostResponse, tags=["Community"])
def create_post(
    post: PostCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db_post = Post(user_id=current_user.id, **post.model_dump())
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    return to_post_response(db_post)


@app.delete("/posts/{post_id}", tags=["Community"])
def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="ไม่พบโพสต์")
    if post.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์ลบโพสต์นี้")
    db.delete(post)
    db.commit()
    return {"message": "ลบโพสต์แล้ว"}


@app.post("/posts/{post_id}/comments", response_model=CommentResponse, tags=["Community"])
def create_comment(
    post_id: int,
    comment: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not db.query(Post).filter(Post.id == post_id).first():
        raise HTTPException(status_code=404, detail="ไม่พบโพสต์")
    db_comment = Comment(post_id=post_id, user_id=current_user.id, content=comment.content)
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return to_comment_response(db_comment)


@app.get("/posts/{post_id}/comments", dependencies=[Depends(get_current_user)], response_model=List[CommentResponse], tags=["Community"])
def list_comments(post_id: int, db: Session = Depends(get_db)):
    if not db.query(Post).filter(Post.id == post_id).first():
        raise HTTPException(status_code=404, detail="ไม่พบโพสต์")
    return [
        to_comment_response(c)
        for c in db.query(Comment)
        .filter(Comment.post_id == post_id)
        .order_by(Comment.created_at.asc())
        .all()
    ]


# ==================== หมอนทอง AI: ผู้ช่วยวิเคราะห์ปัญหาอุปกรณ์สวน ====================
@app.post("/diagnose", dependencies=[Depends(get_current_user)], tags=["Monthong AI"])
async def diagnose(image: UploadFile = File(...)):
    allowed = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
    if image.content_type not in allowed:
        raise HTTPException(status_code=415, detail="รองรับไฟล์ JPG, PNG และ WEBP เท่านั้น")
    raw = await image.read()
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="รูปภาพต้องมีขนาดไม่เกิน 10 MB")
    return {
        "filename": image.filename,
        "problem": "ปั๊มน้ำแรงดันตก",
        "likely_cause": "ใบพัดปั๊มสึกหรือมีสิ่งอุดตันในท่อดูด",
        "confidence": 85,
        "recommendations": [
            "ถอดตรวจใบพัดปั๊มว่าสึกหรือแตกหักหรือไม่",
            "เช็คท่อดูดและตะแกรงกรองว่ามีเศษวัสดุอุดตันหรือไม่",
            "ตรวจซีลกันน้ำว่ารั่วซึมจนอากาศเข้าไปในระบบหรือไม่",
        ],
        "disclaimer": "ผลนี้เป็นการสาธิตการเชื่อมระบบ ไม่ใช่การวินิจฉัยอุปกรณ์จากโมเดลจริง",
    }