import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, ExchangeRate
from database.crud import get_latest_rate, get_rate_history, save_rate_if_changed


@pytest.fixture
def db_session():
    """In-memory SQLite database session fixture for testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_empty_database_returns_none(db_session):
    latest = get_latest_rate(db_session, "USD/IDR")
    assert latest is None


def test_save_rate_first_time(db_session):
    now = datetime.now(timezone.utc)
    record, was_saved = save_rate_if_changed(
        db=db_session,
        pair="USD/IDR",
        price=15750.25,
        change_percent=0.12,
        timestamp=now
    )

    assert was_saved is True
    assert record.id is not None
    assert record.price == 15750.25
    assert record.change_percent == 0.12

    # Verify latest
    latest = get_latest_rate(db_session, "USD/IDR")
    assert latest is not None
    assert latest.price == 15750.25


def test_deduplication_does_not_save_duplicate_rate(db_session):
    now = datetime.now(timezone.utc)
    # Simpan pertama kali
    save_rate_if_changed(db_session, "USD/IDR", 15750.25, 0.12, now)

    # Simpan kedua kali dengan nilai yang SAMA
    record, was_saved = save_rate_if_changed(db_session, "USD/IDR", 15750.25, 0.12, now)

    assert was_saved is False
    assert record.price == 15750.25

    # Total record di database harus tetap 1
    items, total = get_rate_history(db_session, "USD/IDR")
    assert total == 1
    assert len(items) == 1


def test_save_when_rate_changes(db_session):
    now = datetime.now(timezone.utc)
    # Nilai 1
    save_rate_if_changed(db_session, "USD/IDR", 15750.25, 0.12, now)
    # Nilai 2 (Berubah)
    record2, was_saved2 = save_rate_if_changed(db_session, "USD/IDR", 15780.00, 0.25, now)

    assert was_saved2 is True
    assert record2.price == 15780.00

    # Total record sekarang harus 2
    items, total = get_rate_history(db_session, "USD/IDR")
    assert total == 2
    # Item pertama harus data terbaru
    assert items[0].price == 15780.00
    assert items[1].price == 15750.25


def test_pagination_history(db_session):
    now = datetime.now(timezone.utc)
    # Tambahkan 10 data berbeda
    for i in range(10):
        save_rate_if_changed(db_session, "USD/IDR", 15700.0 + i * 10, 0.1 * i, now)

    # Ambil page 1: limit 4, offset 0
    page1, total = get_rate_history(db_session, "USD/IDR", limit=4, offset=0)
    assert total == 10
    assert len(page1) == 4

    # Ambil page 2: limit 4, offset 4
    page2, _ = get_rate_history(db_session, "USD/IDR", limit=4, offset=4)
    assert len(page2) == 4
    # Pastikan data page 2 berbeda dengan page 1
    assert page1[0].id != page2[0].id


def test_prune_old_rates(db_session):
    from database.crud import prune_old_rates
    now = datetime.now(timezone.utc)
    # Masukkan 15 data record
    for i in range(15):
        save_rate_if_changed(db_session, "USD/IDR", 15000.0 + i * 10, 0.01 * i, now)

    _, total_before = get_rate_history(db_session, "USD/IDR", limit=100)
    assert total_before == 15

    # Prune agar hanya tersisa 5 data
    deleted = prune_old_rates(db_session, "USD/IDR", max_keep=5)
    assert deleted == 10

    items_after, total_after = get_rate_history(db_session, "USD/IDR", limit=100)
    assert total_after == 5
    assert len(items_after) == 5
    # Pastikan data yang tersisa adalah data paling baru (harga tertinggi)
    assert items_after[0].price == 15140.0
