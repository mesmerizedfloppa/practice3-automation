"""ПР1. Резервное копирование с ротацией и проверкой целостности.

Вариант 7: хранить последние 8 копий (KEEP_LAST = 8).

Запуск:
    python backup.py            # создать копию, выполнить ротацию, проверить восстановление
    python backup.py verify     # проверить восстановление последней копии
    python backup.py restore    # восстановить данные из последней копии
"""
import hashlib
import json
import shutil
import sys
import tarfile
import time
from datetime import datetime
from pathlib import Path

SOURCE = Path("company_data")   # что копируем
BACKUP_DIR = Path("backups")    # куда складываем архивы
KEEP_LAST = 8                   # сколько последних копий хранить


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def make_manifest(folder):
    """Контрольная сумма каждого файла: {относительный_путь: sha256}."""
    return {str(p.relative_to(folder)): sha256(p)
            for p in sorted(folder.rglob("*")) if p.is_file()}


def manifest_path(archive):
    """backup_XXX.tar.gz -> backup_XXX.json"""
    return archive.with_suffix("").with_suffix(".json")


def create_backup():
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive = BACKUP_DIR / f"backup_{stamp}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(SOURCE, arcname=SOURCE.name)
    manifest = {"created": stamp, "archive_sha256": sha256(archive),
                "files": make_manifest(SOURCE)}
    manifest_path(archive).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Создан {archive.name}, файлов: {len(manifest['files'])}, "
          f"размер: {archive.stat().st_size / 1024:.1f} КБ")
    return archive


def rotate():
    archives = sorted(BACKUP_DIR.glob("backup_*.tar.gz"))
    for old in archives[:-KEEP_LAST]:
        old.unlink()
        manifest_path(old).unlink(missing_ok=True)
        print(f"[ROTATE] Удалена старая копия {old.name}")


def verify_restore(archive):
    """Восстанавливает архив во временную папку и сравнивает контрольные суммы."""
    manifest = json.loads(manifest_path(archive).read_text(encoding="utf-8"))
    if sha256(archive) != manifest["archive_sha256"]:
        print("[FAIL] Архив повреждён: контрольная сумма не совпадает")
        return False

    tmp = Path("restore_test")
    shutil.rmtree(tmp, ignore_errors=True)
    with tarfile.open(archive) as tar:
        tar.extractall(tmp, filter="data")
    restored = make_manifest(tmp / SOURCE.name)
    shutil.rmtree(tmp)

    expected = manifest["files"]
    if restored == expected:
        print(f"[OK] Восстановление проверено: {len(restored)} файлов совпадают")
        return True

    # Задание 3: подробный отчёт о различиях
    missing = sorted(set(expected) - set(restored))   # есть в манифесте, нет в архиве
    extra = sorted(set(restored) - set(expected))     # есть в архиве, нет в манифесте
    changed = sorted(p for p in set(expected) & set(restored)
                     if expected[p] != restored[p])   # хеши не совпадают

    print("[FAIL] Восстановленные данные не совпадают с оригиналом")
    print(f"       отсутствуют: {len(missing)}, лишние: {len(extra)}, "
          f"изменены: {len(changed)}")
    for p in missing:
        print(f"       - отсутствует: {p}")
    for p in extra:
        print(f"       - лишний:      {p}")
    for p in changed:
        print(f"       - изменён:     {p} (в манифесте {expected[p][:12]}…, "
              f"после восстановления {restored[p][:12]}…)")
    return False


def restore(archive):
    """Восстанавливает данные из архива в текущую папку (Задание 4)."""
    start = time.perf_counter()

    # 1. Сначала убеждаемся, что архив цел, и только потом удаляем что-либо
    manifest = json.loads(manifest_path(archive).read_text(encoding="utf-8"))
    if sha256(archive) != manifest["archive_sha256"]:
        print("[FAIL] Архив повреждён, восстановление отменено (данные не тронуты)")
        return False

    # 2. Удаляем повреждённую папку и распаковываем архив на её место
    shutil.rmtree(SOURCE, ignore_errors=True)
    with tarfile.open(archive) as tar:
        tar.extractall(".", filter="data")

    # 3. Сверяем восстановленные файлы с манифестом
    ok = make_manifest(SOURCE) == manifest["files"]
    elapsed = time.perf_counter() - start
    status = ("данные совпадают с манифестом" if ok
              else "ВНИМАНИЕ: данные не совпадают с манифестом")
    print(f"[RESTORE] Восстановлено из {archive.name}: {status}")
    print(f"[RESTORE] Время восстановления: {elapsed:.3f} с")
    return ok


def latest_archive():
    archives = sorted(BACKUP_DIR.glob("backup_*.tar.gz"))
    if not archives:
        sys.exit("Копий нет: сначала выполните python backup.py")
    return archives[-1]


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "backup"
    if command == "backup":
        archive = create_backup()
        rotate()
        verify_restore(archive)
    elif command == "verify":
        verify_restore(latest_archive())
    elif command == "restore":
        restore(latest_archive())
    else:
        print("Использование: python backup.py [backup|verify|restore]")
