from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ExchangeRateResponse(BaseModel):
    """
    Schema JSON response untuk data kurs sesuai format requirement:
    {
      "pair": "USD/IDR",
      "price": 15750.25,
      "change_percent": 0.12,
      "timestamp": "2026-08-19T10:00:00Z"
    }
    """
    model_config = ConfigDict(from_attributes=True)

    pair: str = Field(description="Pasangan mata uang", json_schema_extra={"example": "USD/IDR"})
    price: float = Field(description="Harga kurs terkini", json_schema_extra={"example": 15750.25})
    change_percent: float = Field(description="Persentase perubahan hari ini (%)", json_schema_extra={"example": 0.12})
    timestamp: datetime = Field(description="Waktu pengambilan data kurs (UTC)", json_schema_extra={"example": "2026-08-19T10:00:00Z"})


class ExchangeRateHistoryItem(ExchangeRateResponse):
    """Item record dalam daftar riwayat kurs."""
    id: Optional[int] = Field(default=None, description="ID record di database", json_schema_extra={"example": 1})


class ExchangeRateHistoryResponse(BaseModel):
    """
    Schema JSON response untuk riwayat kurs dengan pagination.
    """
    pair: str = Field(description="Pasangan mata uang", json_schema_extra={"example": "USD/IDR"})
    total: int = Field(description="Total keseluruhan record perubahan di database", json_schema_extra={"example": 150})
    limit: int = Field(description="Jumlah data yang diminta per halaman", json_schema_extra={"example": 10})
    offset: int = Field(description="Offset pagination", json_schema_extra={"example": 0})
    data: List[ExchangeRateHistoryItem] = Field(description="Daftar record kurs historis")


class HealthResponse(BaseModel):
    """Schema response endpoint health check."""
    status: str = Field(description="Status API", json_schema_extra={"example": "ok"})
    database: str = Field(description="Status koneksi database", json_schema_extra={"example": "connected"})
    environment: str = Field(description="Mode environment", json_schema_extra={"example": "development"})
    timestamp: datetime = Field(description="Waktu server saat ini (UTC)", json_schema_extra={"example": "2026-08-19T10:00:00Z"})
    version: str = Field(description="Versi aplikasi", json_schema_extra={"example": "1.0.0"})
