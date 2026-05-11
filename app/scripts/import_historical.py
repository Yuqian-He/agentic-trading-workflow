from app.core.config import settings
from app.services.historical_importer import HistoricalBarImporter


def main() -> None:
    importer = HistoricalBarImporter(settings.bar_db_path)
    result = importer.ensure_seeded(
        file_path=settings.historical_seed_file,
        symbol=settings.historical_seed_symbol,
        interval=settings.historical_seed_interval,
        input_timezone=settings.historical_seed_timezone,
    )
    print(
        {
            "status": result.status,
            "inserted_or_updated": result.inserted_or_updated,
            "scanned_lines": result.scanned_lines,
            "db_min_ts": result.db_min_ts,
            "db_max_ts": result.db_max_ts,
            "file_path": result.file_path,
        }
    )


if __name__ == "__main__":
    main()

