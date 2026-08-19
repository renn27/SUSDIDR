from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from database.models import ExchangeRate
from utils.logger import setup_logger

logger = setup_logger("database_crud")


def get_latest_rate(db: Session, pair: str = "USD/IDR") -> Optional[ExchangeRate]:
    """
    Mengambil data kurs terbaru dari database berdasarkan nama pair mata uang.
    
    Args:
        db (Session): Database session
        pair (str): Pasangan mata uang (default: "USD/IDR")
        
    Returns:
        Optional[ExchangeRate]: Record kurs terakhir atau None jika tabel masih kosong.
    """
    return db.query(ExchangeRate)\
        .filter(ExchangeRate.pair == pair)\
        .order_by(desc(ExchangeRate.id))\
        .first()


def get_rate_history(
    db: Session,
    pair: str = "USD/IDR",
    limit: int = 50,
    offset: int = 0
) -> Tuple[List[ExchangeRate], int]:
    """
    Mengambil riwayat kurs mata uang dengan pagination (limit & offset).
    
    Args:
        db (Session): Database session
        pair (str): Pasangan mata uang (default: "USD/IDR")
        limit (int): Jumlah maksimum record yang diambil
        offset (int): Jumlah record yang dilewati (offset pagination)
        
    Returns:
        Tuple[List[ExchangeRate], int]: (Daftar record kurs, Total seluruh record)
    """
    query = db.query(ExchangeRate).filter(ExchangeRate.pair == pair)
    total_count = query.count()
    items = query.order_by(desc(ExchangeRate.id)).offset(offset).limit(limit).all()
    return items, total_count


def save_rate_if_changed(
    db: Session,
    pair: str,
    price: float,
    change_percent: float,
    timestamp: datetime
) -> Tuple[Optional[ExchangeRate], bool]:
    """
    Memeriksa nilai kurs terbaru di database.
    - Jika nilai kurs BERUBAH (atau belum ada data), simpan record baru.
    - Jika nilai kurs SAMA dengan record terakhir, abaikan penyimpanan untuk mencegah duplikasi.
    
    Args:
        db (Session): Database session
        pair (str): Pasangan mata uang (contoh: "USD/IDR")
        price (float): Harga kurs saat ini
        change_percent (float): Persentase perubahan (%)
        timestamp (datetime): Timestamp waktu pengambilan data
        
    Returns:
        Tuple[Optional[ExchangeRate], bool]: (Instance ExchangeRate, True jika disimpan / False jika diabaikan)
    """
    latest = get_latest_rate(db, pair=pair)

    # Cek apakah data sudah ada dan nilainya sama persis
    if latest is not None and latest.price == price and latest.change_percent == change_percent:
        logger.debug(
            f"Kurs {pair} tidak berubah (Price: {price:,.2f}, Change: {change_percent:+.2f}%). Skip simpan."
        )
        return latest, False

    # Jika harga berubah atau data belum ada sama sekali, buat record baru
    new_record = ExchangeRate(
        pair=pair,
        price=price,
        change_percent=change_percent,
        timestamp=timestamp
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)

    if latest is None:
        logger.info(
            f"Record pertama disimpan -> Pair: {pair} | Price: {price:,.2f} | Change: {change_percent:+.2f}%"
        )
    else:
        diff = price - latest.price
        diff_str = f"+{diff:,.2f}" if diff >= 0 else f"{diff:,.2f}"
        logger.info(
            f"Perubahan kurs terdeteksi -> Pair: {pair} | Baru: {price:,.2f} (Lama: {latest.price:,.2f}, Selisih: {diff_str}) | Change: {change_percent:+.2f}%"
        )

    return new_record, True


def prune_old_rates(db: Session, pair: str = "USD/IDR", max_keep: int = 10000) -> int:
    """
    Menghapus data riwayat yang melebihi batas simpan maksimum agar database
    tetap ringan, cepat, dan tidak menghabiskan memori server.
    
    Args:
        db (Session): Database session
        pair (str): Pasangan mata uang
        max_keep (int): Jumlah record terbaru yang dipertahankan
        
    Returns:
        int: Jumlah baris yang dihapus
    """
    try:
        total = db.query(ExchangeRate).filter(ExchangeRate.pair == pair).count()
        if total > max_keep:
            excess = total - max_keep
            # Cari ID cutoff
            subquery = (
                db.query(ExchangeRate.id)
                .filter(ExchangeRate.pair == pair)
                .order_by(desc(ExchangeRate.id))
                .offset(max_keep)
                .limit(1)
                .subquery()
            )
            cutoff_id = db.query(subquery).scalar()
            if cutoff_id:
                deleted = (
                    db.query(ExchangeRate)
                    .filter(ExchangeRate.pair == pair, ExchangeRate.id <= cutoff_id)
                    .delete(synchronize_session=False)
                )
                db.commit()
                logger.info(f"Database Maintenance: {deleted} record kurs lama berhasil diprune.")
                return deleted
    except Exception as e:
        logger.warning(f"Gagal melakukan pruning database: {e}")
        db.rollback()
    return 0
