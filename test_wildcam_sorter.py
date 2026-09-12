import csv
import os
import sys
import tempfile
import threading
import types
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

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
        self.assertEqual(
            FullScreenViewer.PLAYBACK_RATE_LABELS,
            ('0.5×', '0.75×', '0.8×', '0.9×', '1.0×',
             '1.1×', '1.2×', '1.5×', '2×'),
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

    def test_fit_to_window_uses_available_canvas_size(self):
        viewer = FullScreenViewer.__new__(FullScreenViewer)
        viewer._orig_image = MagicMock()
        viewer._orig_image.size = (4000, 3000)
        viewer.canvas = MagicMock()
        viewer.canvas.winfo_width.return_value = 1200
        viewer.canvas.winfo_height.return_value = 800
        viewer._set_scale = MagicMock()
        viewer._fit_to_window()
        viewer._set_scale.assert_called_once_with((800 / 3000) * 0.95)


class PlatformCompatibilityTests(unittest.TestCase):
    def test_macos_uses_avfoundation_without_directshow(self):
        with patch.multiple(
            wildcam_sorter.cv2,
            CAP_FFMPEG=1900,
            CAP_DSHOW=700,
            CAP_AVFOUNDATION=1200,
            CAP_GSTREAMER=1800,
            CAP_ANY=0,
            create=True,
        ):
            backends = wildcam_sorter.preferred_video_backends('darwin')
        self.assertEqual(backends, [1900, 1200, 0])
        self.assertNotIn(700, backends)

    def test_windows_uses_directshow_without_avfoundation(self):
        with patch.multiple(
            wildcam_sorter.cv2,
            CAP_FFMPEG=1900,
            CAP_DSHOW=700,
            CAP_AVFOUNDATION=1200,
            CAP_GSTREAMER=1800,
            CAP_ANY=0,
            create=True,
        ):
            backends = wildcam_sorter.preferred_video_backends('win32')
        self.assertEqual(backends, [1900, 700, 0])
        self.assertNotIn(1200, backends)

    def test_windows_short_path_is_never_called_on_macos(self):
        with patch.object(wildcam_sorter.sys, 'platform', 'darwin'):
            self.assertEqual(wildcam_sorter._windows_short_path('/tmp/测试.mp4'), '')


class FullscreenDispatchTests(unittest.TestCase):
    def test_video_in_nonfirst_panel_opens_video_player(self):
        app = WildCamSorter.__new__(WildCamSorter)
        app.current_group_files = ['001.jpg', '002.jpg', '003.jpg', '004.mp4']
        app.video_playing = False
        app.root = MagicMock()

        viewer = MagicMock()
        with patch.object(wildcam_sorter, 'FullScreenViewer', return_value=viewer) as viewer_cls:
            app._open_fullscreen(3)

        viewer_cls.assert_called_once_with(app.root, '004.mp4', is_video=True)
        app.root.wait_window.assert_called_once_with(viewer.window)


class CaptureModeGroupingTests(unittest.TestCase):
    def _make_files(self, folder, names):
        paths = []
        for name in names:
            path = os.path.join(folder, name)
            with open(path, 'wb'):
                pass
            paths.append(path)
        return paths

    def test_video_first_groups_by_configured_counts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            names = [
                '001.mp4', '002.jpg', '003.jpg', '004.jpg',
                '005.mp4', '006.jpg', '007.jpg', '008.jpg',
            ]
            self._make_files(temp_dir, names)
            groups = wildcam_sorter.scan_and_group_files(
                temp_dir, 3, 1, wildcam_sorter.ORDER_VIDEOS_FIRST
            )
            self.assertEqual(
                [[os.path.basename(path) for path in group] for group in groups],
                [names[:4], names[4:]],
            )
            self.assertTrue(all(
                wildcam_sorter.group_matches_capture_pattern(
                    group, 3, 1, wildcam_sorter.ORDER_VIDEOS_FIRST
                ) for group in groups
            ))

    def test_photos_first_and_every_file_appears_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            names = [
                '001.jpg', '002.jpg', '003.jpg', '004.mp4',
                '005.jpg', '006.jpg', '007.jpg', '008.mp4',
            ]
            self._make_files(temp_dir, names)
            groups = wildcam_sorter.scan_and_group_files(
                temp_dir, 3, 1, wildcam_sorter.ORDER_PHOTOS_FIRST
            )
            flattened = [os.path.basename(path) for group in groups for path in group]
            self.assertEqual(flattened, names)
            self.assertEqual(len(flattened), len(set(flattened)))
            self.assertTrue(all(
                wildcam_sorter.group_matches_capture_pattern(
                    group, 3, 1, wildcam_sorter.ORDER_PHOTOS_FIRST
                ) for group in groups
            ))

    def test_photo_only_mode_keeps_incomplete_last_group(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            names = [f'{index:03d}.jpg' for index in range(1, 9)]
            self._make_files(temp_dir, names)
            groups = wildcam_sorter.scan_and_group_files(
                temp_dir, 3, 0, wildcam_sorter.ORDER_PHOTOS_FIRST
            )
            self.assertEqual([len(group) for group in groups], [3, 3, 2])
            flattened = [os.path.basename(path) for group in groups for path in group]
            self.assertEqual(flattened, names)
            self.assertFalse(wildcam_sorter.group_matches_capture_pattern(
                groups[-1], 3, 0, wildcam_sorter.ORDER_PHOTOS_FIRST
            ))

    def test_pattern_validation_detects_wrong_order(self):
        group = ['001.mp4', '002.jpg', '003.jpg', '004.jpg']
        self.assertFalse(wildcam_sorter.group_matches_capture_pattern(
            group, 3, 1, wildcam_sorter.ORDER_PHOTOS_FIRST
        ))

    def test_capture_mode_rejects_both_counts_zero(self):
        with self.assertRaises(ValueError):
            wildcam_sorter.validate_capture_mode(
                0, 0, wildcam_sorter.ORDER_PHOTOS_FIRST
            )

    def test_large_scan_uses_lazy_groups_and_reports_progress(self):
        class FakeEntry:
            def __init__(self, name):
                self.name = name

            def is_file(self, follow_symlinks=False):
                return True

        class FakeScandir:
            def __init__(self, count):
                self.count = count

            def __iter__(self):
                for index in range(self.count):
                    yield FakeEntry(f'IMG_{index:06d}.jpg')

            def close(self):
                pass

        progress = []
        with patch.object(wildcam_sorter.os, 'scandir', return_value=FakeScandir(100_000)):
            groups = wildcam_sorter.scan_and_group_files(
                'X:/huge-camera-folder', 3, 1,
                wildcam_sorter.ORDER_PHOTOS_FIRST,
                progress_callback=lambda *values: progress.append(values),
            )

        self.assertIsInstance(groups, wildcam_sorter.MediaGroupSequence)
        self.assertEqual(groups.total_files, 100_000)
        self.assertEqual(len(groups), 25_000)
        self.assertEqual(
            [os.path.basename(path) for path in groups[-1]],
            ['IMG_099996.jpg', 'IMG_099997.jpg', 'IMG_099998.jpg', 'IMG_099999.jpg'],
        )
        self.assertGreaterEqual(len(progress), 100)

    def test_large_scan_can_be_cancelled(self):
        class FakeEntry:
            name = '001.jpg'

            def is_file(self, follow_symlinks=False):
                return True

        class FakeScandir:
            def __iter__(self):
                for _ in range(10_000):
                    yield FakeEntry()

            def close(self):
                pass

        cancel_event = threading.Event()
        cancel_event.set()
        with patch.object(wildcam_sorter.os, 'scandir', return_value=FakeScandir()):
            with self.assertRaises(wildcam_sorter.ScanCancelled):
                wildcam_sorter.scan_and_group_files(
                    'X:/huge-camera-folder', 3, 1,
                    wildcam_sorter.ORDER_PHOTOS_FIRST,
                    cancel_event=cancel_event,
                )


class MediaJumpTests(unittest.TestCase):
    def setUp(self):
        self.groups = wildcam_sorter.MediaGroupSequence(
            'X:/camera',
            ['001.mp4', '002.jpg', '003.jpg', '004.jpg',
             'IMG_0199.mp4', 'IMG_0200.jpg', 'IMG_0201.jpg', 'IMG_0202.jpg'],
            4,
        )

    def test_sequence_number_uses_last_numeric_part(self):
        self.assertEqual(wildcam_sorter.media_sequence_number('CAM_2026_0200.JPG'), 200)
        self.assertIsNone(wildcam_sorter.media_sequence_number('camera.jpg'))

    def test_numeric_jump_finds_its_group(self):
        group_index, _, finished = wildcam_sorter.search_media_group_chunk(
            self.groups, '200', chunk_size=20
        )
        self.assertEqual(group_index, 1)
        self.assertTrue(finished)

    def test_jump_search_can_continue_in_chunks(self):
        group_index, next_index, finished = wildcam_sorter.search_media_group_chunk(
            self.groups, 'IMG_0202.jpg', start_index=0, chunk_size=4
        )
        self.assertIsNone(group_index)
        self.assertEqual(next_index, 4)
        self.assertFalse(finished)

        group_index, _, finished = wildcam_sorter.search_media_group_chunk(
            self.groups, 'IMG_0202.jpg', start_index=next_index, chunk_size=4
        )
        self.assertEqual(group_index, 1)
        self.assertTrue(finished)


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

    def test_new_classification_appends_without_rewriting_large_csv(self):
        metadata = {
            'longitude': None, 'latitude': None,
            'altitude': None, 'datetime': None,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = os.path.join(temp_dir, 'POINT_02')
            os.makedirs(source_dir)
            csv_path = os.path.join(temp_dir, 'wildcam_records.csv')
            with open(csv_path, 'w', newline='', encoding='utf-8-sig') as handle:
                writer = csv.DictWriter(handle, fieldnames=wildcam_sorter.CSV_HEADERS)
                writer.writeheader()
                writer.writerow({header: '' for header in wildcam_sorter.CSV_HEADERS})
            inode_before = os.stat(csv_path).st_ino

            app = self._make_app(
                temp_dir, source_dir, [os.path.join(source_dir, '100001.jpg')]
            )
            with patch.object(wildcam_sorter, 'extract_gps_from_file',
                              return_value=metadata.copy()):
                app._write_csv_record('赤狐', replace_existing=False)

            self.assertEqual(os.stat(csv_path).st_ino, inode_before)
            with open(csv_path, newline='', encoding='utf-8-sig') as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[-1]['文件名'], '100001.jpg')


if __name__ == '__main__':
    unittest.main()
