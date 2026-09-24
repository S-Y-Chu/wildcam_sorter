import csv
import os
import sys
import tempfile
import threading
import types
import unittest
from types import SimpleNamespace
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
        viewer.zoom_level = 7.0
        viewer._pan_x = 12
        viewer._pan_y = 30
        viewer._update_display = MagicMock()
        viewer._fit_to_window()
        self.assertEqual(viewer.zoom_level, 1.0)
        self.assertEqual((viewer._pan_x, viewer._pan_y), (0.0, 0.0))
        viewer._update_display.assert_called_once_with()

    def test_wheel_speed_changes_zoom_rate(self):
        slow = FullScreenViewer.__new__(FullScreenViewer)
        slow._last_wheel_time = 1.0
        fast = FullScreenViewer.__new__(FullScreenViewer)
        fast._last_wheel_time = 1.0
        with patch.object(wildcam_sorter.time, 'monotonic', return_value=1.2):
            slow_factor = slow._wheel_factor(120)
        with patch.object(wildcam_sorter.time, 'monotonic', return_value=1.02):
            fast_factor = fast._wheel_factor(120)
        self.assertGreater(fast_factor, slow_factor)


class PlatformCompatibilityTests(unittest.TestCase):
    def test_viewer_stays_on_screen_when_parent_is_macos_fullscreen(self):
        parent = MagicMock()
        parent.winfo_width.return_value = 1920
        parent.winfo_height.return_value = 1080
        parent.winfo_rootx.return_value = 0
        parent.winfo_rooty.return_value = 0
        parent.state.return_value = 'normal'
        parent.attributes.return_value = True
        self.assertEqual(wildcam_sorter.viewer_window_bounds(parent, 1920, 1080),
                         (1200, 800, 360, 140))
        parent.geometry.assert_not_called()
        self.assertTrue(wildcam_sorter.mac_parent_is_fullscreen(parent, 1920, 1080))

    def test_viewer_is_smaller_than_windows_maximized_parent(self):
        parent = MagicMock()
        parent.winfo_width.return_value = 1800
        parent.winfo_height.return_value = 950
        parent.winfo_rootx.return_value = 10
        parent.winfo_rooty.return_value = 15
        parent.state.return_value = 'zoomed'
        parent.attributes.return_value = False
        self.assertEqual(wildcam_sorter.viewer_window_bounds(parent, 1920, 1080),
                         (1200, 800, 360, 140))
        self.assertFalse(wildcam_sorter.mac_parent_is_fullscreen(parent, 1920, 1080))
        parent.state.return_value = 'normal'
        self.assertEqual(wildcam_sorter.viewer_window_bounds(parent, 1920, 1080),
                         (1200, 800, 360, 140))

    def test_native_mac_fullscreen_detected_if_tk_flag_not_set(self):
        parent = MagicMock()
        parent.winfo_width.return_value = 1920
        parent.winfo_height.return_value = 1024
        parent.winfo_rootx.return_value = 0
        parent.winfo_rooty.return_value = 0
        parent.attributes.return_value = False
        self.assertTrue(wildcam_sorter.mac_parent_is_fullscreen(parent, 1920, 1080))

    def test_viewer_stays_centered_for_small_parent(self):
        parent = MagicMock()
        parent.winfo_width.return_value = 1000
        parent.winfo_height.return_value = 700
        parent.state.return_value = 'normal'
        parent.attributes.return_value = False
        self.assertEqual(wildcam_sorter.viewer_window_bounds(parent, 1920, 1080),
                         (1200, 800, 360, 140))

    def test_warning_color_changes_with_theme_even_for_later_messages(self):
        app = WildCamSorter.__new__(WildCamSorter)
        app.settings = {'theme': 'light'}
        app._active_theme = 'light'
        self.assertEqual(app._theme_color('#FFB74D'), '#8A4B00')
        app._active_theme = 'dark'
        self.assertEqual(app._theme_color('#FFB74D'), '#FFB74D')

    def test_rebuilding_species_avoids_dark_rows_in_light_theme(self):
        app = WildCamSorter.__new__(WildCamSorter)
        app.species_frame = MagicMock()
        app.species_frame.winfo_children.return_value = []
        app.species_buttons = {}
        app._species_tiles = {}
        app._editing_categories = False
        app.species_list = ['牛', '羊']
        app.root = MagicMock()
        app._panels = []
        app.overflow_panels = []
        app._active_theme = 'light'
        app.settings = {'theme': 'light'}
        app._apply_theme = MagicMock()
        with patch.object(wildcam_sorter, 'create_button') as button_factory, \
                patch.object(wildcam_sorter.tk, 'Frame') as frame_factory:
            app._rebuild_species_buttons()
        self.assertEqual(button_factory.call_count, 4)
        self.assertEqual(frame_factory.call_count, 2)
        self.assertEqual(len(app._species_tiles), 2)
        app._apply_theme.assert_called_once_with('light', persist=False,
                                                  window=app.species_frame)

    def test_opening_viewer_only_themes_the_viewer_not_the_parent(self):
        app = WildCamSorter.__new__(WildCamSorter)
        app.current_group_files = ['/tmp/1.jpg']
        app.root = MagicMock()
        app.settings = {'theme': 'light'}
        app.video_playing = False
        app._apply_theme = MagicMock()
        viewer = MagicMock()
        with patch.object(wildcam_sorter, 'FullScreenViewer', return_value=viewer):
            app._open_fullscreen(0)
        app._apply_theme.assert_called_once_with('light', persist=False,
                                                  window=viewer.window)
        app.root.geometry.assert_not_called()

    def test_macos_native_buttons_use_dark_readable_text(self):
        button = MagicMock()

        result = wildcam_sorter.ensure_macos_button_readability(button, 'darwin')

        self.assertIs(result, button)
        button.configure.assert_called_once_with(
            foreground=wildcam_sorter.MACOS_BUTTON_TEXT,
            activeforeground=wildcam_sorter.MACOS_BUTTON_ACTIVE_TEXT,
            disabledforeground=wildcam_sorter.MACOS_BUTTON_DISABLED_TEXT,
        )

    def test_non_macos_button_colors_are_not_overridden(self):
        button = MagicMock()

        result = wildcam_sorter.ensure_macos_button_readability(button, 'win32')

        self.assertIs(result, button)
        button.configure.assert_not_called()

    def test_button_factory_applies_macos_contrast_fix(self):
        button = MagicMock()
        parent = MagicMock()
        with patch.object(wildcam_sorter.sys, 'platform', 'darwin'), \
                patch.object(wildcam_sorter.tk, 'Button', return_value=button) as button_cls:
            result = wildcam_sorter.create_button(
                parent, text='教程', bg='#1565C0', fg='white'
            )

        self.assertIs(result, button)
        button_cls.assert_called_once_with(
            parent, text='教程', bg='#1565C0', fg='white'
        )
        self.assertEqual(
            button.configure.call_args.kwargs['foreground'],
            wildcam_sorter.MACOS_BUTTON_TEXT,
        )

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


class CaptureSuggestionTests(unittest.TestCase):
    def test_suggests_two_contiguous_camera_modes(self):
        pattern = 'viii' * 50 + 'iiiv' * 100
        names = [f'{n:04d}.' + ('mp4' if kind == 'v' else 'jpg')
                 for n, kind in enumerate(pattern, 1)]
        segments = wildcam_sorter.suggest_capture_segments(names)
        self.assertEqual([(s['start'], s['end'], s['order']) for s in segments], [
            (1, 200, wildcam_sorter.ORDER_VIDEOS_FIRST),
            (201, 600, wildcam_sorter.ORDER_PHOTOS_FIRST),
        ])

    def test_does_not_guess_photos_per_group_from_photos_only(self):
        self.assertEqual(wildcam_sorter.suggest_capture_segments(
            [f'{n:03d}.jpg' for n in range(100)]), [])

    def test_ranges_are_disjoint_and_use_file_ordinals(self):
        names = ['001.mp4', '002.jpg', '003.jpg', '004.jpg',
                 '005.jpg', '006.mp4', '007.jpg', '008.jpg',
                 '009.mp4', '010.jpg', '011.jpg', '012.jpg',
                 '013.jpg', '014.mp4', '015.jpg', '016.jpg']
        groups = wildcam_sorter.RangedMediaGroupSequence('/tmp', names, [{
            'start': 1, 'end': 16, 'photo_count': 3, 'video_count': 1,
            'order': wildcam_sorter.ORDER_VIDEOS_FIRST,
        }])
        count, ranges = wildcam_sorter.capture_mismatch_ranges(groups)
        self.assertEqual((count, ranges), (2, [(5, 8), (13, 16)]))

    def test_ignores_macos_appledouble_files_when_scanning(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ('001.mp4', '002.jpg', '._003.mp4', '003.jpg'):
                open(os.path.join(folder, name), 'wb').close()
            scanned = wildcam_sorter.scan_and_group_files(folder)
            self.assertEqual(scanned.file_names, ['001.mp4', '002.jpg', '003.jpg'])

    def test_seek_requests_decode_without_blocking_tk_thread(self):
        viewer = FullScreenViewer.__new__(FullScreenViewer)
        viewer._video_duration = 120
        viewer.video_progress_var = MagicMock()
        viewer.video_progress_var.get.return_value = 45
        viewer._video_commands = wildcam_sorter.queue.Queue()
        viewer._seeking = True
        viewer._video_cap = MagicMock()
        viewer._on_seek_end()
        self.assertEqual(viewer._video_commands.get_nowait(), ('seek', 45))
        viewer._video_cap.set.assert_not_called()
        viewer._video_cap.read.assert_not_called()

    def test_decoder_catches_up_to_wall_clock_when_frames_are_late(self):
        commands, results = wildcam_sorter.queue.Queue(), wildcam_sorter.queue.Queue(maxsize=3)
        stopped = threading.Event()
        capture = MagicMock()
        capture.get.side_effect = lambda prop: {11: 25, 12: 1000, 13: 0}.get(prop, 0)
        def read_one():
            stopped.set()
            return True, object()
        capture.read.side_effect = read_one
        with patch.object(wildcam_sorter, 'open_video_capture', return_value=capture), \
             patch.object(wildcam_sorter.cv2, 'CAP_PROP_FPS', 11, create=True), \
             patch.object(wildcam_sorter.cv2, 'CAP_PROP_FRAME_COUNT', 12, create=True), \
             patch.object(wildcam_sorter.cv2, 'CAP_PROP_POS_FRAMES', 13, create=True), \
             patch.object(wildcam_sorter.cv2, 'CAP_PROP_POS_MSEC', 14, create=True), \
             patch.object(wildcam_sorter.cv2, 'COLOR_BGR2RGB', 15, create=True), \
             patch.object(wildcam_sorter.cv2, 'cvtColor', return_value=object(), create=True), \
             patch.object(wildcam_sorter.Image, 'fromarray', return_value=MagicMock()), \
             patch.object(wildcam_sorter.time, 'monotonic', side_effect=[0, 4, 4, 4]):
            FullScreenViewer._viewer_decode_worker('/camera/video.mp4', commands,
                                                    results, stopped)
        # The slow player seeks to the media position associated with the
        # frame clock, while the viewer starts at 0.5x.
        capture.set.assert_any_call(14, 2000)
        capture.release.assert_called_once()



class PreviewPipelineTests(unittest.TestCase):
    def _make_app(self):
        app = WildCamSorter.__new__(WildCamSorter)
        app._image_preview_queue = wildcam_sorter.queue.PriorityQueue()
        app._video_preview_queue = wildcam_sorter.queue.PriorityQueue(maxsize=32)
        app._preview_result_queue = wildcam_sorter.queue.Queue()
        app._preview_poll_after_id = None
        app._preview_task_sequence = 0
        app._preview_pending = set()
        app._preview_completed_panels = set()
        app._preview_pending_images = 0
        app._preview_cache = wildcam_sorter.OrderedDict()
        app._preview_cache_lock = threading.Lock()
        app._pending_video_start = None
        app._autoplay_video_preview_ready = False
        app._video_start_after_id = None
        app._preview_generation = 1
        app._closing = False
        app.root = MagicMock()
        app.root.after.return_value = 'after-id'
        return app

    def test_default_preview_workers_have_two_video_decoders(self):
        self.assertEqual(wildcam_sorter.IMAGE_PREVIEW_WORKERS, 4)
        self.assertEqual(wildcam_sorter.VIDEO_PREVIEW_WORKERS, 2)


    def test_image_and_video_previews_use_separate_queues(self):
        app = self._make_app()
        image_panel = MagicMock(index=3)
        image_panel._calc_display_size.return_value = (640, 400)
        video_panel = MagicMock(index=0)
        video_panel._calc_display_size.return_value = (640, 400)

        app._queue_preview(image_panel, '/camera/004.jpg', 1)
        app._queue_preview(video_panel, '/camera/001.mp4', 1)

        self.assertEqual(app._image_preview_queue.qsize(), 1)
        self.assertEqual(app._video_preview_queue.qsize(), 1)
        image_job = app._image_preview_queue.get_nowait()
        video_job = app._video_preview_queue.get_nowait()
        self.assertEqual(image_job[4], '/camera/004.jpg')
        self.assertEqual(video_job[4], '/camera/001.mp4')

    def test_polling_continues_while_last_job_is_in_flight(self):
        app = self._make_app()
        app._preview_pending.add((1, 3, '/camera/004.jpg'))

        app._poll_preview_results()

        app.root.after.assert_called_once_with(20, app._poll_preview_results)
        self.assertEqual(app._preview_poll_after_id, 'after-id')

    def test_video_autoplay_starts_with_first_frame_even_if_photos_are_loading(self):
        app = self._make_app()
        panel = MagicMock()
        app._pending_video_start = (1, '/camera/001.mp4', panel)
        app._preview_pending_images = 1
        app._autoplay_video_preview_ready = False
        app._start_video_if_current = MagicMock()

        app._maybe_start_pending_video(1)
        app._start_video_if_current.assert_not_called()

        app._autoplay_video_preview_ready = True
        app._maybe_start_pending_video(1)
        app._start_video_if_current.assert_called_once_with(
            1, '/camera/001.mp4', panel
        )

    def test_image_decoder_returns_target_sized_preview(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, 'large.jpg')
            wildcam_sorter.Image.new('RGB', (2400, 1600), 'green').save(path)
            preview = WildCamSorter._decode_image_preview(path, 600, 400)

        self.assertLessEqual(preview.width, 600)
        self.assertLessEqual(preview.height, 400)

    def test_prefetched_small_thumbnail_is_shown_then_replaced_at_full_size(self):
        app = self._make_app()
        path = '/camera/004.jpg'
        app._preview_cache[(path, 320, 200)] = wildcam_sorter.Image.new('RGB', (300, 200))
        panel = MagicMock(index=3)
        panel._calc_display_size.return_value = (900, 450)

        app._queue_preview(panel, path, 1)

        thumbnail = app._preview_result_queue.get_nowait()
        self.assertTrue(thumbnail[-1])  # visible immediately, but provisional
        self.assertEqual(thumbnail[-2], (900, 450))
        job = app._image_preview_queue.get_nowait()
        self.assertEqual(job[5:7], (900, 450))
        self.assertEqual(panel._preview_target_size, (900, 450))

    def test_provisional_preview_does_not_finish_pending_full_size_job(self):
        app = self._make_app()
        panel = MagicMock(index=3, file_path='/camera/004.jpg')
        panel._preview_target_size = (900, 450)
        app._panel_for_index = MagicMock(return_value=panel)
        app._preview_pending.add((1, 3, '/camera/004.jpg'))
        app._preview_pending_images = 1
        image = wildcam_sorter.Image.new('RGB', (600, 450))
        preliminary = (1, 3, '/camera/004.jpg', image, None, 'image',
                       '创建：今天', (900, 450), True)
        app._preview_result_queue.put(preliminary)
        with patch.object(wildcam_sorter.ImageTk, 'PhotoImage', return_value=MagicMock()):
            app._poll_preview_results()
            self.assertIn((1, 3, '/camera/004.jpg'), app._preview_pending)
            self.assertEqual(app._preview_pending_images, 1)
            app._preview_result_queue.put(preliminary[:-1] + (False,))
            app._poll_preview_results()
        self.assertFalse(app._preview_pending)
        self.assertEqual(app._preview_pending_images, 0)


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

    def test_ranged_modes_and_selected_range(self):
        names = [f'{index:03d}.jpg' for index in range(1, 13)]
        segments = [
            {'start': 1, 'end': 6, 'photo_count': 2, 'video_count': 0,
             'order': wildcam_sorter.ORDER_PHOTOS_FIRST},
            {'start': 7, 'end': 12, 'photo_count': 3, 'video_count': 0,
             'order': wildcam_sorter.ORDER_PHOTOS_FIRST},
        ]
        groups = wildcam_sorter.RangedMediaGroupSequence(
            'X:/camera', names, segments, selection_start=3, selection_end=10
        )
        self.assertEqual(
            [[os.path.basename(path) for path in group] for group in groups],
            [['003.jpg', '004.jpg'], ['005.jpg', '006.jpg'],
             ['007.jpg', '008.jpg', '009.jpg'], ['010.jpg']],
        )
        self.assertEqual(groups.all_group_count, 5)


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


class ClassificationQueueTests(unittest.TestCase):
    def _make_app(self, target_dir, source_dir, files):
        app = WildCamSorter.__new__(WildCamSorter)
        app.target_dir = target_dir
        app.source_dir = source_dir
        app.current_group_files = files
        app.selected_flags = [True] * len(files)
        app.per_file_species = {}
        app._log = lambda *args, **kwargs: None
        return app

    def test_ten_rapid_jobs_are_all_copied_and_recorded_in_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = os.path.join(temp_dir, 'source')
            target_dir = os.path.join(temp_dir, 'output')
            os.makedirs(source_dir)
            os.makedirs(target_dir)
            app = WildCamSorter.__new__(WildCamSorter)
            app._classify_queue = wildcam_sorter.queue.Queue()
            app._classify_result_queue = wildcam_sorter.queue.Queue()
            app._log = lambda *args, **kwargs: None
            worker = threading.Thread(target=app._classification_worker)
            worker.start()

            for index in range(10):
                file_path = os.path.join(source_dir, f'{index + 1:03d}.jpg')
                with open(file_path, 'wb') as handle:
                    handle.write(b'test')
                app._classify_queue.put({
                    'group_index': index,
                    'rel_path': f'source/{index + 1:03d}.jpg',
                    'files': (file_path,),
                    'selected': (True,),
                    'per_file_species': {},
                    'categories': ('赤狐',),
                    'target_dir': target_dir,
                    'point_name': 'source',
                    'old_dest_files': (),
                    'replace_existing': False,
                })
            app._classify_queue.put(None)
            worker.join(timeout=10)
            self.assertFalse(worker.is_alive())

            results = [app._classify_result_queue.get_nowait() for _ in range(10)]
            self.assertEqual([item['job']['group_index'] for item in results], list(range(10)))
            self.assertTrue(all(not item['errors'] for item in results))
            with open(os.path.join(target_dir, 'wildcam_records.csv'),
                      newline='', encoding='utf-8-sig') as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 10)
            self.assertEqual([row['文件名'] for row in rows],
                             [f'{index + 1:03d}.jpg' for index in range(10)])

    def test_manual_output_files_are_backfilled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = os.path.join(temp_dir, 'POINT')
            target_dir = os.path.join(temp_dir, 'output')
            category_dir = os.path.join(target_dir, '牛')
            os.makedirs(source_dir)
            os.makedirs(category_dir)
            source_file = os.path.join(source_dir, '001.jpg')
            output_file = os.path.join(category_dir, '001.jpg')
            Image = wildcam_sorter.Image
            Image.new('RGB', (2, 2)).save(source_file)
            wildcam_sorter.shutil.copy2(source_file, output_file)
            count = wildcam_sorter.backfill_manual_csv(
                source_dir, target_dir, {'001.jpg': [('牛', output_file)]}
            )
            self.assertEqual(count, 1)
            with open(os.path.join(target_dir, 'wildcam_records.csv'),
                      newline='', encoding='utf-8-sig') as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]['文件名'], '001.jpg')
            self.assertEqual(rows[0]['物种名'], '牛')

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


class Version112Tests(unittest.TestCase):
    def test_layout_supports_three_five_and_nine_files(self):
        three = wildcam_sorter.media_panel_layout(3, 2)
        self.assertEqual(three[0], (2, 0, 0, 2, 6))
        five = wildcam_sorter.media_panel_layout(5, 4)
        self.assertEqual(five[0], (4, 0, 0, 2, 4))
        self.assertEqual({cell[0] for cell in five}, set(range(5)))
        self.assertEqual(len(wildcam_sorter.media_panel_layout(9)), 9)

    def test_five_photos_use_three_plus_two_and_equal_mode_removes_big_cell(self):
        normal = wildcam_sorter.media_panel_layout(5)
        self.assertEqual([(x[1], x[4]) for x in normal],
                         [(0, 4), (0, 4), (0, 4), (1, 6), (1, 6)])
        equal = wildcam_sorter.media_panel_layout(5, video_index=4, equal=True)
        self.assertEqual([item[4] for item in equal], [4] * 5)
        self.assertEqual(equal[4][0], 4)  # no video promotion in equal mode

    def test_drag_positions_reflow_and_order_is_saved_on_release(self):
        app = WildCamSorter.__new__(WildCamSorter)
        app._editing_categories = True
        app._migration_pending = False
        app.settings = {'theme': 'dark'}
        app._active_theme = 'dark'
        app._press_after_id = None
        app._category_drag_name = '狼'
        app._category_drag_offset = 30
        app._category_order_changed = False
        app.species_list = ['狼', '鹿']
        app._category_widths = {'狼': 80, '鹿': 80}
        app._category_slot_x = {'狼': 0, '鹿': 86}
        app._category_visual_x = {'狼': 0, '鹿': 86}
        app._species_tiles = {'狼': (MagicMock(), MagicMock()),
                              '鹿': (MagicMock(), MagicMock())}
        app.species_canvas = MagicMock()
        app.species_canvas.winfo_rootx.return_value = 0
        app.species_canvas.winfo_width.return_value = 300
        app.species_frame = MagicMock()
        app.species_frame.winfo_rootx.return_value = 0
        app.species_frame.winfo_width.return_value = 300
        app.root = MagicMock()
        app._animate_category_tiles = MagicMock()
        with tempfile.TemporaryDirectory() as directory:
            app.target_dir = directory
            app._drag_category('狼', SimpleNamespace(x_root=175))
            self.assertEqual(app.species_list, ['鹿', '狼'])
            self.assertEqual(app._category_slot_x, {'鹿': 0, '狼': 86})
            app._end_category_press()
            self.assertEqual(wildcam_sorter.ordered_categories(
                directory, ['狼', '鹿']), ['鹿', '狼'])
        app._animate_category_tiles.assert_called()

    def test_neighbors_slide_toward_target_instead_of_jumping(self):
        app = WildCamSorter.__new__(WildCamSorter)
        app._editing_categories = True
        app._category_animation_after_id = None
        app._category_drag_name = '狼'
        app._category_slot_x = {'鹿': 0, '狼': 86}
        app._category_visual_x = {'狼': 90.0, '鹿': 86.0}
        tile = MagicMock()
        app._species_tiles = {'狼': (MagicMock(), MagicMock()),
                              '鹿': (tile, MagicMock())}
        app.root = MagicMock()
        app.root.after.return_value = 'animation-id'

        app._animate_category_tiles()

        self.assertGreater(app._category_visual_x['鹿'], 0)
        self.assertLess(app._category_visual_x['鹿'], 86)
        self.assertEqual(app._category_animation_after_id, 'animation-id')
        tile.place_configure.assert_called_once()

    def test_category_order_persists_and_includes_external_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            wildcam_sorter.save_category_order(directory, ['狼', '牛'])
            self.assertEqual(wildcam_sorter.ordered_categories(
                directory, ['牛', '鹿', '狼']), ['狼', '牛', '鹿'])

    def test_category_migration_updates_files_csv_history_and_aliases(self):
        with tempfile.TemporaryDirectory() as directory:
            src = os.path.join(directory, '狼')
            dst = os.path.join(directory, '鹿')
            os.makedirs(src)
            os.makedirs(dst)
            with open(os.path.join(src, '001.jpg'), 'wb') as handle:
                handle.write(b'image')
            csv_path = os.path.join(directory, 'wildcam_records.csv')
            with open(csv_path, 'w', encoding='utf-8-sig', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=wildcam_sorter.CSV_HEADERS)
                writer.writeheader()
                writer.writerow({'文件名': '001.jpg', '物种名': '狼；鹿'})
            count = wildcam_sorter.migrate_category_storage(directory, '狼', '鹿')
            self.assertEqual(count, 1)
            self.assertFalse(os.path.exists(src))
            self.assertTrue(os.path.isfile(os.path.join(dst, '001.jpg')))
            with open(csv_path, encoding='utf-8-sig', newline='') as handle:
                self.assertEqual(list(csv.DictReader(handle))[0]['物种名'], '鹿')
            original = {'a': {'species': '狼、鹿',
                              'dest_files': [os.path.join(src, '001.jpg')]}}
            actual = wildcam_sorter.reconcile_category_history(original, directory)
            self.assertEqual(actual['a']['species'], '鹿')
            self.assertEqual(actual['a']['dest_files'], [os.path.join(dst, '001.jpg')])

    def test_collision_aborts_migration_before_changing_csv_or_files(self):
        with tempfile.TemporaryDirectory() as directory:
            for category, contents in (('狼', b'one'), ('鹿', b'two')):
                folder = os.path.join(directory, category)
                os.makedirs(folder)
                with open(os.path.join(folder, '001.jpg'), 'wb') as handle:
                    handle.write(contents)
            csv_path = os.path.join(directory, 'wildcam_records.csv')
            with open(csv_path, 'w', encoding='utf-8') as handle:
                handle.write('物种名\n狼\n')
            with self.assertRaises(FileExistsError):
                wildcam_sorter.migrate_category_storage(directory, '狼', '鹿')
            self.assertTrue(os.path.exists(os.path.join(directory, '狼', '001.jpg')))
            with open(csv_path, encoding='utf-8') as handle:
                self.assertEqual(handle.read(), '物种名\n狼\n')

    def test_migration_rolls_back_files_if_csv_commit_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            src = os.path.join(directory, '狼')
            dst = os.path.join(directory, '鹿')
            os.makedirs(src)
            os.makedirs(dst)
            source_file = os.path.join(src, '002.jpg')
            with open(source_file, 'wb') as handle:
                handle.write(b'original')
            csv_path = os.path.join(directory, 'wildcam_records.csv')
            with open(csv_path, 'w', encoding='utf-8') as handle:
                handle.write('物种名\n狼\n')
            actual_replace = os.replace
            def fail_csv(source, target):
                if target == csv_path and '.migration-' in source:
                    raise OSError('simulated CSV disk error')
                return actual_replace(source, target)
            with patch.object(wildcam_sorter.os, 'replace', side_effect=fail_csv):
                with self.assertRaisesRegex(OSError, 'simulated'):
                    wildcam_sorter.migrate_category_storage(directory, '狼', '鹿')
            self.assertTrue(os.path.isfile(source_file))
            self.assertFalse(os.path.exists(os.path.join(dst, '002.jpg')))
            with open(csv_path, encoding='utf-8') as handle:
                self.assertEqual(handle.read(), '物种名\n狼\n')

    def test_main_space_classifies_and_viewer_blocks_shortcut(self):
        app = WildCamSorter.__new__(WildCamSorter)
        app.current_group_files = ['001.jpg']
        app._viewer_open = False
        app._scan_dialog = None
        app._last_space_classify = 0
        app.root = MagicMock()
        app.root.focus_get.return_value = None
        app._on_empty = MagicMock()
        app._on_main_space()
        app._on_empty.assert_called_once()
        app._viewer_open = True
        app._on_main_space()
        app._on_empty.assert_called_once()

    def test_main_preview_autoplay_rate_and_viewer_half_speed(self):
        self.assertEqual(wildcam_sorter.MAIN_VIDEO_RATE, 5.0)
        self.assertEqual(wildcam_sorter.MAIN_VIDEO_DISPLAY_FPS, 20.0)


if __name__ == '__main__':
    unittest.main()
