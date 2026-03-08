#!/usr/bin/env python3
"""Tests for CLI automation scripts.

Run with: pytest scripts/tests/test_cli.py -v
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# =============================================================================
# Tests for daily_drawing.py
# =============================================================================

class TestGetLatestLocalDate:
    """Tests for get_latest_local_date function."""

    def test_returns_none_for_nonexistent_dir(self, tmp_path):
        from daily_drawing import get_latest_local_date
        nonexistent = tmp_path / "nonexistent"
        assert get_latest_local_date(nonexistent) is None

    def test_returns_none_for_empty_dir(self, tmp_path):
        from daily_drawing import get_latest_local_date
        assert get_latest_local_date(tmp_path) is None

    def test_returns_none_for_no_matching_files(self, tmp_path):
        from daily_drawing import get_latest_local_date
        (tmp_path / "random_file.jpg").touch()
        (tmp_path / "not-a-date.jpg").touch()
        assert get_latest_local_date(tmp_path) is None

    def test_finds_single_date(self, tmp_path):
        from daily_drawing import get_latest_local_date
        (tmp_path / "2024-03-15_1.jpg").touch()
        result = get_latest_local_date(tmp_path)
        assert result == datetime(2024, 3, 15)

    def test_finds_most_recent_date(self, tmp_path):
        from daily_drawing import get_latest_local_date
        (tmp_path / "2024-01-01_1.jpg").touch()
        (tmp_path / "2024-06-15_1.jpg").touch()
        (tmp_path / "2024-03-10_1.jpg").touch()
        result = get_latest_local_date(tmp_path)
        assert result == datetime(2024, 6, 15)

    def test_ignores_directories(self, tmp_path):
        from daily_drawing import get_latest_local_date
        (tmp_path / "2024-12-31_subdir").mkdir()
        (tmp_path / "2024-01-01_1.jpg").touch()
        result = get_latest_local_date(tmp_path)
        assert result == datetime(2024, 1, 1)


class TestGetLocalDateCounts:
    """Tests for get_local_date_counts function."""

    def test_returns_empty_for_nonexistent_dir(self, tmp_path):
        from daily_drawing import get_local_date_counts
        nonexistent = tmp_path / "nonexistent"
        assert get_local_date_counts(nonexistent) == {}

    def test_returns_empty_for_empty_dir(self, tmp_path):
        from daily_drawing import get_local_date_counts
        assert get_local_date_counts(tmp_path) == {}

    def test_counts_single_image_per_date(self, tmp_path):
        from daily_drawing import get_local_date_counts
        (tmp_path / "2024-03-15_1.jpg").touch()
        (tmp_path / "2024-03-16_1.jpg").touch()
        result = get_local_date_counts(tmp_path)
        assert result == {"2024-03-15": 1, "2024-03-16": 1}

    def test_counts_multiple_images_per_date(self, tmp_path):
        from daily_drawing import get_local_date_counts
        (tmp_path / "2024-03-15_1.jpg").touch()
        (tmp_path / "2024-03-15_2.jpg").touch()
        (tmp_path / "2024-03-15_3.jpg").touch()
        (tmp_path / "2024-03-16_1.jpg").touch()
        result = get_local_date_counts(tmp_path)
        assert result == {"2024-03-15": 3, "2024-03-16": 1}

    def test_ignores_non_matching_files(self, tmp_path):
        from daily_drawing import get_local_date_counts
        (tmp_path / "2024-03-15_1.jpg").touch()
        (tmp_path / "random.jpg").touch()
        (tmp_path / "README.md").touch()
        result = get_local_date_counts(tmp_path)
        assert result == {"2024-03-15": 1}


class TestUpdateFrontmatterWithTweet:
    """Tests for update_frontmatter_with_tweet function."""

    def test_adds_tweet_url_to_frontmatter(self, tmp_path):
        from daily_drawing import update_frontmatter_with_tweet
        md_file = tmp_path / "test.md"
        md_file.write_text("""---
layout: drawing
filename: 2024-03-15_1.jpg
date: 2024-03-15
tags:
---
""")
        update_frontmatter_with_tweet(md_file, "https://x.com/user/status/123")
        content = md_file.read_text()
        assert "tweet: https://x.com/user/status/123" in content
        assert content.index("tweet:") < content.index("tags:")

    def test_does_not_duplicate_tweet_url(self, tmp_path):
        from daily_drawing import update_frontmatter_with_tweet
        md_file = tmp_path / "test.md"
        original = """---
layout: drawing
tweet: https://x.com/user/status/existing
tags:
---
"""
        md_file.write_text(original)
        update_frontmatter_with_tweet(md_file, "https://x.com/user/status/new")
        content = md_file.read_text()
        assert content == original  # Unchanged


class TestFetchGoodnightTweets:
    """Tests for fetch_goodnight_tweets with mocked HTTP."""

    @patch('daily_drawing.requests.get')
    def test_returns_tweets_with_media(self, mock_get):
        from daily_drawing import fetch_goodnight_tweets

        # Mock tweets response
        tweets_response = MagicMock()
        tweets_response.status_code = 200
        tweets_response.json.return_value = [
            {"tweet_id": "123", "created_at": "2024-03-15T22:00:00+00:00"},
            {"tweet_id": "456", "created_at": "2024-03-16T22:00:00+00:00"},
        ]

        # Mock media responses
        media_response_1 = MagicMock()
        media_response_1.status_code = 200
        media_response_1.json.return_value = [{"media_url": "https://example.com/img1.jpg"}]

        media_response_2 = MagicMock()
        media_response_2.status_code = 200
        media_response_2.json.return_value = [{"media_url": "https://example.com/img2.jpg"}]

        mock_get.side_effect = [tweets_response, media_response_1, media_response_2]

        result = fetch_goodnight_tweets(datetime(2024, 1, 1))

        assert len(result) == 2
        assert result[0]["id"] == "123"
        assert result[0]["image_url"] == "https://example.com/img1.jpg"
        assert result[1]["id"] == "456"

    @patch('daily_drawing.requests.get')
    def test_skips_tweets_without_media(self, mock_get):
        from daily_drawing import fetch_goodnight_tweets

        tweets_response = MagicMock()
        tweets_response.status_code = 200
        tweets_response.json.return_value = [
            {"tweet_id": "123", "created_at": "2024-03-15T22:00:00+00:00"},
        ]

        media_response = MagicMock()
        media_response.status_code = 200
        media_response.json.return_value = []  # No media

        mock_get.side_effect = [tweets_response, media_response]

        result = fetch_goodnight_tweets(datetime(2024, 1, 1))
        assert len(result) == 0

    @patch('daily_drawing.requests.get')
    def test_exits_on_api_error(self, mock_get):
        from daily_drawing import fetch_goodnight_tweets

        error_response = MagicMock()
        error_response.status_code = 500
        error_response.text = "Internal Server Error"
        mock_get.return_value = error_response

        with pytest.raises(SystemExit):
            fetch_goodnight_tweets(datetime(2024, 1, 1))


class TestDownloadImage:
    """Tests for download_image with mocked HTTP."""

    @patch('daily_drawing.requests.get')
    def test_downloads_image_successfully(self, mock_get, tmp_path):
        from daily_drawing import download_image

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake image data"
        mock_get.return_value = mock_response

        dest = tmp_path / "test.jpg"
        download_image("https://example.com/image.jpg", dest)

        assert dest.exists()
        assert dest.read_bytes() == b"fake image data"

    @patch('daily_drawing.requests.get')
    def test_exits_on_download_error(self, mock_get, tmp_path):
        from daily_drawing import download_image

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        with pytest.raises(SystemExit):
            download_image("https://example.com/missing.jpg", tmp_path / "test.jpg")


class TestGitCommit:
    """Tests for git_commit message formatting."""

    @patch('daily_drawing.subprocess.run')
    def test_single_drawing_message(self, mock_run):
        from daily_drawing import git_commit
        mock_run.return_value = MagicMock(returncode=0)

        git_commit(["2024-03-15_1"])

        # Check commit message
        commit_call = mock_run.call_args_list[1]
        assert "Add drawing 2024-03-15_1" in str(commit_call)

    @patch('daily_drawing.subprocess.run')
    def test_multiple_drawings_same_date_message(self, mock_run):
        from daily_drawing import git_commit
        mock_run.return_value = MagicMock(returncode=0)

        git_commit(["2024-03-15_1", "2024-03-15_2"])

        commit_call = mock_run.call_args_list[1]
        assert "Add 2 drawings (2024-03-15)" in str(commit_call)

    @patch('daily_drawing.subprocess.run')
    def test_multiple_drawings_date_range_message(self, mock_run):
        from daily_drawing import git_commit
        mock_run.return_value = MagicMock(returncode=0)

        git_commit(["2024-03-15_1", "2024-03-16_1", "2024-03-17_1"])

        commit_call = mock_run.call_args_list[1]
        assert "Add 3 drawings (2024-03-15 to 2024-03-17)" in str(commit_call)


class TestDailyDrawingIntegration:
    """Integration tests for daily_drawing workflow logic."""

    @patch('daily_drawing.run_pipeline')
    @patch('daily_drawing.download_image')
    @patch('daily_drawing.fetch_goodnight_tweets')
    def test_skips_existing_dates(self, mock_fetch, mock_download, mock_pipeline, tmp_path, monkeypatch):
        """Dates with existing images should be skipped."""
        import daily_drawing
        monkeypatch.setattr(daily_drawing, 'DRAWINGS_DIR', tmp_path / 'drawings')
        monkeypatch.setattr(daily_drawing, 'METADATA_DIR', tmp_path / '_drawings')

        # Create existing image
        drawings_dir = tmp_path / 'drawings'
        drawings_dir.mkdir()
        (drawings_dir / '2024-03-15_1.jpg').touch()

        # Mock API returning tweet for existing date
        mock_fetch.return_value = [
            {'id': '123', 'created_at': '2024-03-15T22:00:00+00:00', 'image_url': 'http://example.com/img.jpg'}
        ]

        daily_drawing.daily_drawing(since='2024-03-01')

        # Should not download (date already exists)
        mock_download.assert_not_called()

    @patch('daily_drawing.run_pipeline')
    @patch('daily_drawing.download_image')
    @patch('daily_drawing.fetch_goodnight_tweets')
    def test_downloads_multiple_tweets_same_day(self, mock_fetch, mock_download, mock_pipeline, tmp_path, monkeypatch):
        """Multiple tweets on same day should get incrementing suffixes."""
        import daily_drawing
        monkeypatch.setattr(daily_drawing, 'DRAWINGS_DIR', tmp_path / 'drawings')
        monkeypatch.setattr(daily_drawing, 'METADATA_DIR', tmp_path / '_drawings')

        drawings_dir = tmp_path / 'drawings'
        drawings_dir.mkdir()
        (tmp_path / '_drawings').mkdir()

        # Mock API returning 2 tweets on same date
        mock_fetch.return_value = [
            {'id': '456', 'created_at': '2024-03-15T23:00:00+00:00', 'image_url': 'http://example.com/img2.jpg'},
            {'id': '123', 'created_at': '2024-03-15T22:00:00+00:00', 'image_url': 'http://example.com/img1.jpg'},
        ]

        daily_drawing.daily_drawing(since='2024-03-01')

        # Should download both with different suffixes
        assert mock_download.call_count == 2
        call_paths = [str(call[0][1]) for call in mock_download.call_args_list]
        assert any('2024-03-15_1.jpg' in p for p in call_paths)
        assert any('2024-03-15_2.jpg' in p for p in call_paths)

    @patch('daily_drawing.run_pipeline')
    @patch('daily_drawing.download_image')
    @patch('daily_drawing.fetch_goodnight_tweets')
    def test_force_redownloads_existing(self, mock_fetch, mock_download, mock_pipeline, tmp_path, monkeypatch):
        """Force flag should re-download even if date exists."""
        import daily_drawing
        monkeypatch.setattr(daily_drawing, 'DRAWINGS_DIR', tmp_path / 'drawings')
        monkeypatch.setattr(daily_drawing, 'METADATA_DIR', tmp_path / '_drawings')

        drawings_dir = tmp_path / 'drawings'
        drawings_dir.mkdir()
        (drawings_dir / '2024-03-15_1.jpg').touch()
        (tmp_path / '_drawings').mkdir()

        mock_fetch.return_value = [
            {'id': '123', 'created_at': '2024-03-15T22:00:00+00:00', 'image_url': 'http://example.com/img.jpg'}
        ]

        daily_drawing.daily_drawing(since='2024-03-01', force=True)

        # Should download (force ignores existing)
        mock_download.assert_called_once()


# =============================================================================
# Tests for generate_image_metadata.py
# =============================================================================

class TestGenerateImageMetadata:
    """Tests for generate_md_for_images function."""

    def test_creates_metadata_for_matching_images(self, tmp_path):
        from generate_image_metadata import generate_md_for_images

        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()

        (source / "2024-03-15_test.jpg").touch()
        (source / "2024-03-16_another.png").touch()

        count = generate_md_for_images(str(source), str(dest), "drawing")

        assert count == 2
        assert (dest / "2024-03-15_test.md").exists()
        assert (dest / "2024-03-16_another.md").exists()

        content = (dest / "2024-03-15_test.md").read_text()
        assert "layout: drawing" in content
        assert "filename: 2024-03-15_test.jpg" in content
        assert "date: 2024-03-15" in content

    def test_skips_existing_metadata_files(self, tmp_path):
        from generate_image_metadata import generate_md_for_images

        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()

        (source / "2024-03-15_test.jpg").touch()
        (dest / "2024-03-15_test.md").write_text("existing content")

        count = generate_md_for_images(str(source), str(dest), "drawing")

        assert count == 0
        assert (dest / "2024-03-15_test.md").read_text() == "existing content"

    def test_ignores_non_matching_files(self, tmp_path):
        from generate_image_metadata import generate_md_for_images

        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()

        (source / "random_file.jpg").touch()
        (source / "2024-03-15.jpg").touch()  # Missing suffix
        (source / "README.md").touch()

        count = generate_md_for_images(str(source), str(dest), "drawing")
        assert count == 0

    def test_returns_zero_for_nonexistent_source(self, tmp_path):
        from generate_image_metadata import generate_md_for_images
        count = generate_md_for_images(str(tmp_path / "nonexistent"), str(tmp_path / "dest"), "drawing")
        assert count == 0


# =============================================================================
# Tests for generate_tags.py
# =============================================================================

class TestExtractTags:
    """Tests for extract_tags function."""

    def test_extracts_tags_from_collection(self, tmp_path, monkeypatch):
        from generate_tags import extract_tags

        # Change to tmp_path so relative paths work
        monkeypatch.chdir(tmp_path)

        # Create config
        config = tmp_path / "_config.yml"
        config.write_text("""
collections:
  drawings:
    output: true
""")

        # Create collection directory with files
        drawings = tmp_path / "_drawings"
        drawings.mkdir()
        (drawings / "test1.md").write_text("""---
layout: drawing
tags:
  - nature
  - abstract
---
""")
        (drawings / "test2.md").write_text("""---
layout: drawing
tags:
  - portrait
  - nature
---
""")

        tags = extract_tags(str(config))
        assert tags == {"nature", "abstract", "portrait"}

    def test_handles_empty_tags(self, tmp_path, monkeypatch):
        from generate_tags import extract_tags

        monkeypatch.chdir(tmp_path)

        config = tmp_path / "_config.yml"
        config.write_text("collections: {}")

        tags = extract_tags(str(config))
        assert tags == set()


class TestGenerateTagPages:
    """Tests for generate_tag_pages function."""

    def test_creates_tag_page_files(self, tmp_path):
        from generate_tags import generate_tag_pages

        output = tmp_path / "tags"
        tags = {"Nature", "Abstract Art", "portrait"}

        count = generate_tag_pages(tags, str(output))

        assert count == 3
        assert (output / "nature.md").exists()
        assert (output / "abstract-art.md").exists()
        assert (output / "portrait.md").exists()

        content = (output / "nature.md").read_text()
        assert "layout: tag" in content
        assert "tag: Nature" in content


# =============================================================================
# Tests for rename_images.py
# =============================================================================

class TestRenameImages:
    """Tests for rename_images function."""

    def test_renames_date_only_files(self, tmp_path):
        from rename_images import rename_images

        (tmp_path / "2024-03-15.jpg").touch()
        (tmp_path / "2024-03-16.jpg").touch()

        count = rename_images(str(tmp_path))

        assert count == 2
        assert (tmp_path / "2024-03-15_1.jpg").exists()
        assert (tmp_path / "2024-03-16_1.jpg").exists()
        assert not (tmp_path / "2024-03-15.jpg").exists()

    def test_increments_suffix_when_exists(self, tmp_path):
        from rename_images import rename_images

        (tmp_path / "2024-03-15.jpg").touch()
        (tmp_path / "2024-03-15_1.jpg").touch()  # Already exists

        count = rename_images(str(tmp_path))

        assert count == 1
        assert (tmp_path / "2024-03-15_1.jpg").exists()  # Original
        assert (tmp_path / "2024-03-15_2.jpg").exists()  # Renamed

    def test_handles_time_suffix_in_filename(self, tmp_path):
        from rename_images import rename_images

        (tmp_path / "2024-03-15 12.30.45.jpg").touch()
        (tmp_path / "2024-03-15_14.00.00.jpg").touch()

        count = rename_images(str(tmp_path))

        assert count == 2
        assert (tmp_path / "2024-03-15_1.jpg").exists()
        assert (tmp_path / "2024-03-15_2.jpg").exists()

    def test_ignores_already_suffixed_files(self, tmp_path):
        from rename_images import rename_images

        (tmp_path / "2024-03-15_1.jpg").touch()
        (tmp_path / "2024-03-15_hello.jpg").touch()

        count = rename_images(str(tmp_path))
        assert count == 0

    def test_returns_zero_for_nonexistent_dir(self, tmp_path):
        from rename_images import rename_images
        count = rename_images(str(tmp_path / "nonexistent"))
        assert count == 0
