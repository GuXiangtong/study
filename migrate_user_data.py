"""
数据迁移脚本：将现有文件目录从扁平结构迁移到按 user_id 隔离的结构。

旧结构：
  DATA_DIR/{学科}/{考试}/xxx.png
  ANALYSIS_DIR/{学科}/xxx.md

新结构：
  DATA_DIR/{user_id}/{学科}/{考试}/xxx.png
  ANALYSIS_DIR/{user_id}/{学科}/xxx.md

执行前请备份数据目录。执行后旧目录不会自动删除，需手动清理。
"""

import os
import shutil
import sqlite3
import sys

from config import DATA_DIR, DATABASE_PATH, ANALYSIS_DIR, SUBJECTS


def migrate():
    if not os.path.exists(DATABASE_PATH):
        print(f"数据库不存在：{DATABASE_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ── 1. 迁移题目图片 ──────────────────────────────────────────────
    print("=== 迁移题目图片 ===")
    rows = cur.execute(
        "SELECT q.id, q.image_path, q.user_id, e.name as exam_name, "
        "s.name as subject_name "
        "FROM questions q "
        "JOIN exams e ON q.exam_id = e.id "
        "JOIN subjects s ON e.subject_id = s.id "
        "WHERE q.image_path IS NOT NULL AND q.user_id IS NOT NULL"
    ).fetchall()

    moved = 0
    skipped = 0
    for row in rows:
        user_id = row['user_id']
        image_path = row['image_path']  # subject/exam/filename

        old_full = os.path.join(DATA_DIR, image_path)
        new_full = os.path.join(DATA_DIR, str(user_id), image_path)

        if not os.path.isfile(old_full):
            # 已经迁移过，或文件不存在
            skipped += 1
            continue

        if os.path.isfile(new_full):
            # 目标已存在，跳过
            skipped += 1
            continue

        os.makedirs(os.path.dirname(new_full), exist_ok=True)
        shutil.copy2(old_full, new_full)
        moved += 1
        print(f"  [图片] {image_path}  →  {user_id}/{image_path}")

    print(f"图片迁移：已复制 {moved} 个，跳过 {skipped} 个\n")

    # ── 2. 迁移分析结果文件 ──────────────────────────────────────────
    print("=== 迁移分析结果文件 ===")
    analysis_rows = cur.execute(
        "SELECT id, file_path, user_id FROM analysis_results "
        "WHERE file_path IS NOT NULL AND user_id IS NOT NULL"
    ).fetchall()

    moved_a = 0
    skipped_a = 0
    for row in analysis_rows:
        user_id = row['user_id']
        file_path = row['file_path']  # subject/filename.md

        old_full = os.path.join(ANALYSIS_DIR, file_path)
        new_full = os.path.join(ANALYSIS_DIR, str(user_id), file_path)

        if not os.path.isfile(old_full):
            skipped_a += 1
            continue

        if os.path.isfile(new_full):
            skipped_a += 1
            continue

        os.makedirs(os.path.dirname(new_full), exist_ok=True)
        shutil.copy2(old_full, new_full)
        moved_a += 1
        print(f"  [分析] {file_path}  →  {user_id}/{file_path}")

    print(f"分析文件迁移：已复制 {moved_a} 个，跳过 {skipped_a} 个\n")

    conn.close()

    print("迁移完成。")
    print("请验证新目录结构后，手动删除旧的扁平目录：")
    for subj in SUBJECTS:
        old_dir = os.path.join(DATA_DIR, subj)
        if os.path.isdir(old_dir):
            print(f"  rm -rf \"{old_dir}\"")
    old_analysis_dirs = [
        os.path.join(ANALYSIS_DIR, subj)
        for subj in SUBJECTS
        if os.path.isdir(os.path.join(ANALYSIS_DIR, subj))
    ]
    for d in old_analysis_dirs:
        print(f"  rm -rf \"{d}\"")


if __name__ == '__main__':
    print("注意：此脚本只复制文件，不删除旧文件。请先备份数据目录。")
    answer = input("继续？(y/N) ").strip().lower()
    if answer == 'y':
        migrate()
    else:
        print("已取消。")
