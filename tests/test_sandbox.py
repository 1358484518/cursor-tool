"""路径沙箱测试：禁止逃出用户指定文件夹。"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from workstation.sandbox import PathDeniedError, is_inside, normalize_root, resolve_in_root


class SandboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "work"
        self.root.mkdir()
        (self.root / "src").mkdir()
        (self.root / "src" / "main.c").write_text("int main(){return 0;}\n", encoding="utf-8")
        self.outside = Path(self._tmp.name) / "secret.txt"
        self.outside.write_text("nope\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_normalize_root(self) -> None:
        self.assertEqual(normalize_root(self.root), self.root.resolve())

    def test_relative_inside(self) -> None:
        path = resolve_in_root("src/main.c", self.root)
        self.assertEqual(path, (self.root / "src" / "main.c").resolve())

    def test_dot_is_root(self) -> None:
        self.assertEqual(resolve_in_root(".", self.root), self.root.resolve())
        self.assertEqual(resolve_in_root("", self.root), self.root.resolve())

    def test_parent_escape_denied(self) -> None:
        with self.assertRaises(PathDeniedError):
            resolve_in_root("../secret.txt", self.root)

    def test_absolute_outside_denied(self) -> None:
        with self.assertRaises(PathDeniedError):
            resolve_in_root(str(self.outside), self.root)

    def test_absolute_inside_allowed(self) -> None:
        target = self.root / "src" / "main.c"
        self.assertEqual(resolve_in_root(str(target), self.root), target.resolve())

    def test_nested_dotdot_denied(self) -> None:
        with self.assertRaises(PathDeniedError):
            resolve_in_root("src/../../secret.txt", self.root)

    def test_symlink_escape_denied(self) -> None:
        link = self.root / "leak"
        try:
            os.symlink(self.outside, link)
        except (OSError, NotImplementedError):
            self.skipTest("当前环境不能创建符号链接")
        with self.assertRaises(PathDeniedError):
            resolve_in_root("leak", self.root)

    def test_is_inside_root_itself(self) -> None:
        self.assertTrue(is_inside(self.root, self.root))


if __name__ == "__main__":
    unittest.main()
