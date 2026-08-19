from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, DateTime, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class ExchangeRate(Base):
    """
    Model database untuk menyimpan data historis kurs mata uang.
    Sesuai requirement: schema mencakup id, harga, persen perubahan, timestamp.
    Tersedia kolom 'pair' untuk kemudahan ekstensi multi-mata uang di masa depan.
    """
    __tablename__ = "exchange_rates"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    pair = Column(String(20), default="USD/IDR", index=True, nullable=False)
    price = Column(Float, nullable=False, comment="Harga/kurs terkini")
    change_percent = Column(Float, nullable=False, comment="Persentase perubahan hari ini (%)")
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True, comment="Waktu pengambilan data")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self) -> dict:
        """
        Mengonversi model instance ke format dictionary terstruktur.
        """
        return {
            "id": self.id,
            "pair": self.pair,
            "price": self.price,
            "change_percent": self.change_percent,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self) -> str:
        return f"<ExchangeRate(id={self.id}, pair='{self.pair}', price={self.price}, change={self.change_percent}%, timestamp='{self.timestamp}')>"
