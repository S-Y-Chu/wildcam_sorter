import csv
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime
from unittest.mock import patch

# 测试CSV和纯逻辑时不需要真正解码视频；CI若未安装OpenCV，提供最小导入替身。
try:
    import cv2  # noqa: F401
except ImportError:
    sys.modules['cv2'] = types.ModuleType('cv2')

try:
    import numpy  # noqa: F401
except ImportError:
    sys.modules['numpy'] = types.ModuleType('numpy')

import wildcam_sorter
from wildcam_sorter import FullScreenViewer, WildCamSorter


class FullScreenViewerTests(unittest.TestCase):
    def test_required_playback_rates_are_available(self):
        self.assertEqual(
            FullScreenViewer.PLAYBACK_RATES,
            (0.5, 0.75, 0.8, 0.9, 1.0, 1.1, 1.2, 1.5, 2.0),
        )

    def test_video_time_format(self):
        self.assertEqual(FullScreenViewer._format_video_time(0), "00:00")
        self.assertEqual(FullScreenViewer._format_video_time(65.9), "01:05")
        self.assertEqual(FullScreenViewer._format_video_time(3661), "1:01:01")

    def test_frame_interval_uses_source_fps_and_selected_rate(self):
        viewer = FullScreenViewer.__new__(FullScreenViewer)
        viewer._video_fps = 30.0
        viewer._playback_rate = 1.0
        self.assertAlmostEqual(viewer._frame_interval(), 1 / 30)
        viewer._playback_rate = 2.0
        self.assertAlmostEqual(viewer._frame_interval(), 1 / 60)


class CsvRecordTests(unittest.TestCase):
    def _make_app(self, target_dir, source_dir, files):
        app = WildCamSorter.__new__(WildCamSorter)
        app.target_dir = target_dir
        app.source_dir = source_dir
        app.current_group_files = files
        app.selected_flags = [True] * len(files)
        app.per_file_species = {}
        app._log = lambda *args, **kwargs: None
        return app

    def test_every_media_file_has_one_row_and_reclassification_updates(self):
        metadata = {
            'longitude': 103.5,
            'latitude': 30.264,
            'altitude': 450.5,
            'datetime': datetime(2024, 6, 15, 14, 30),
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = os.path.join(temp_dir, "100_L59")
            os.makedirs(source_dir)
            files = [
                os.path.join(source_dir, "001.mp4"),
                os.path.join(source_dir, "002.jpg"),
                os.path.join(source_dir, "003.jpg"),
            ]
            app = self._make_app(temp_dir, source_dir, files)

            with patch.object(wildcam_sorter, 'extract_gps_from_file', return_value=metadata.copy()):
                app._write_csv_record("赤狐")

                csv_path = os.path.join(temp_dir, "wildcam_records.csv")
                with open(csv_path, newline='', encoding='utf-8-sig') as handle:
                    first_rows = list(csv.DictReader(handle))
                self.assertEqual([row['文件名'] for row in first_rows], [
                    "001.mp4", "002.jpg", "003.jpg"
                ])
                self.assertEqual([row['物种名'] for row in first_rows], ["赤狐"] * 3)

                app.per_file_species[1] = {"牛", "人"}
                app.selected_flags[2] = False
                app._write_csv_record("赤狐")

            with open(csv_path, newline='', encoding='utf-8-sig') as handle:
                updated_rows = list(csv.DictReader(handle))
            self.assertEqual(len(updated_rows), 3)
            by_name = {row['文件名']: row for row in updated_rows}
            self.assertEqual(by_name['001.mp4']['物种名'], "赤狐")
            self.assertEqual(set(by_name['002.jpg']['物种名'].split('；')), {"牛", "人"})
            self.assertEqual(by_name['003.jpg']['物种名'], "空拍")

    def test_old_csv_is_backed_up_before_new_schema_is_written(self):
        metadata = {
            'longitude': None,
            'latitude': None,
            'altitude': None,
            'datetime': None,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = os.path.join(temp_dir, "POINT_01")
            os.makedirs(source_dir)
            file_path = os.path.join(source_dir, "001.jpg")
            csv_path = os.path.join(temp_dir, "wildcam_records.csv")
            with open(csv_path, 'w', newline='', encoding='utf-8-sig') as handle:
                writer = csv.writer(handle)
                writer.writerow(['经度', '纬度', '海拔高度(m)', '物种名', '拍摄时间', '点位名称'])
                writer.writerow(['', '', '', '赤狐', '', 'POINT_01'])

            app = self._make_app(temp_dir, source_dir, [file_path])
            with patch.object(wildcam_sorter, 'extract_gps_from_file', return_value=metadata.copy()):
                app._write_csv_record("赤狐")

            backups = [
                name for name in os.listdir(temp_dir)
                if name.startswith('wildcam_records_旧格式备份_') and name.endswith('.csv')
            ]
            self.assertEqual(len(backups), 1)
            with open(csv_path, newline='', encoding='utf-8-sig') as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['文件名'], "001.jpg")


if __name__ == '__main__':
    unittest.main()
