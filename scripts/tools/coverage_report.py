#!/usr/bin/env python3
"""
测试覆盖率报告生成脚本

此脚本用于生成项目的完整测试覆盖率报告，包括：
- 运行所有测试并收集覆盖率数据
- 生成 HTML 和 XML 格式的报告
- 输出详细的覆盖率统计信息（代码行/分支/文件）

使用方法：
    python scripts/tools/coverage_report.py [选项]

选项：
    --open      生成报告后在浏览器中打开 HTML 报告
    --no-run    跳过测试运行，仅解析已有的 coverage.xml
    --output    指定报告输出目录（默认: coverage_report）
"""

import argparse
import platform
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

# 覆盖率等级阈值常量
COVERAGE_EXCELLENT = 80
COVERAGE_GOOD = 60
COVERAGE_MEDIUM = 40
COVERAGE_LOW = 20

# 文件筛选阈值
MIN_LINES_FOR_SUGGESTION = 50


@dataclass
class FileCoverage:
    """单个文件的覆盖率数据"""

    name: str
    line_rate: float
    branch_rate: float
    lines_covered: int
    lines_total: int
    branches_covered: int
    branches_total: int

    @property
    def status(self) -> str:
        """根据覆盖率返回状态标识"""
        rate = self.line_rate * 100
        if rate >= COVERAGE_EXCELLENT:
            return "✅ 优秀"
        if rate >= COVERAGE_GOOD:
            return "👍 良好"
        if rate >= COVERAGE_MEDIUM:
            return "⚠️ 中等"
        if rate >= COVERAGE_LOW:
            return "📉 较低"
        return "❌ 需改进"


@dataclass
class CoverageReport:
    """完整的覆盖率报告"""

    files: list[FileCoverage]
    total_lines_covered: int
    total_lines: int
    total_branches_covered: int
    total_branches: int
    line_rate: float
    branch_rate: float

    @property
    def file_count(self) -> int:
        """返回文件数量"""
        return len(self.files)

    def get_distribution(self) -> dict[str, int]:
        """获取覆盖率分布统计"""
        dist = {"excellent": 0, "good": 0, "medium": 0, "low": 0, "poor": 0}
        for f in self.files:
            rate = f.line_rate * 100
            if rate >= COVERAGE_EXCELLENT:
                dist["excellent"] += 1
            elif rate >= COVERAGE_GOOD:
                dist["good"] += 1
            elif rate >= COVERAGE_MEDIUM:
                dist["medium"] += 1
            elif rate >= COVERAGE_LOW:
                dist["low"] += 1
            else:
                dist["poor"] += 1
        return dist


def get_project_root() -> Path:
    """获取项目根目录"""
    script_path = Path(__file__).resolve()
    # 脚本位于 scripts/tools/ 下，向上两级即为项目根目录
    return script_path.parent.parent.parent


def run_tests_with_coverage(project_root: Path, output_dir: str) -> bool:
    """运行测试并收集覆盖率数据"""
    print("=" * 60)
    print("🧪 运行测试并收集覆盖率数据...")
    print("=" * 60)

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
        "--tb=short",
        f"--cov={project_root / 'src'}",
        "--cov-report=term",
        f"--cov-report=html:{output_dir}",
        "--cov-report=xml:coverage.xml",
        "--cov-branch",
    ]

    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            cwd=project_root,
            capture_output=False,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        print("❌ 错误: 未找到 pytest，请确保已安装测试依赖")
        print("   运行: uv pip install -e '.[dev]'")
        return False
    except Exception as e:  # noqa: BLE001
        print(f"❌ 运行测试时出错: {e}")
        return False
    else:
        return result.returncode == 0


def parse_coverage_xml(project_root: Path) -> CoverageReport | None:
    """解析 coverage.xml 文件"""
    xml_path = project_root / "coverage.xml"

    if not xml_path.exists():
        print(f"❌ 错误: 未找到 {xml_path}")
        print("   请先运行测试生成覆盖率数据")
        return None

    try:
        tree = ET.parse(xml_path)  # noqa: S314
        root = tree.getroot()

        # 获取总体覆盖率
        line_rate = float(root.get("line-rate", 0))
        branch_rate = float(root.get("branch-rate", 0))

        # 统计总行数和分支数
        total_lines = 0
        total_lines_covered = 0
        total_branches = 0
        total_branches_covered = 0
        files: list[FileCoverage] = []

        src_prefix = str(project_root / "src") + "/"

        for package in root.findall(".//package"):
            for cls in package.findall("classes/class"):
                filename = cls.get("filename", "")

                # 提取相对于 src 的路径
                rel_name = filename.removeprefix(src_prefix)

                file_line_rate = float(cls.get("line-rate", 0))
                file_branch_rate = float(cls.get("branch-rate", 0))

                # 统计行覆盖
                lines = cls.findall("lines/line")
                file_lines_total = len(lines)
                file_lines_covered = sum(
                    1 for line in lines if int(line.get("hits", 0)) > 0
                )

                # 统计分支覆盖
                file_branches_total = 0
                file_branches_covered = 0
                for line in lines:
                    if line.get("branch") == "true":
                        condition = line.get("condition-coverage", "")
                        if condition:
                            # condition-coverage 格式为 "50% (1/2)"
                            parts = condition.split("(")
                            if len(parts) > 1:
                                nums = parts[1].rstrip(")").split("/")
                                if len(nums) == 2:  # noqa: PLR2004
                                    file_branches_covered += int(nums[0])
                                    file_branches_total += int(nums[1])

                files.append(
                    FileCoverage(
                        name=rel_name,
                        line_rate=file_line_rate,
                        branch_rate=file_branch_rate,
                        lines_covered=file_lines_covered,
                        lines_total=file_lines_total,
                        branches_covered=file_branches_covered,
                        branches_total=file_branches_total,
                    ),
                )

                total_lines += file_lines_total
                total_lines_covered += file_lines_covered
                total_branches += file_branches_total
                total_branches_covered += file_branches_covered

        # 按文件名排序
        files.sort(key=lambda f: f.name)

        return CoverageReport(
            files=files,
            total_lines_covered=total_lines_covered,
            total_lines=total_lines,
            total_branches_covered=total_branches_covered,
            total_branches=total_branches,
            line_rate=line_rate,
            branch_rate=branch_rate,
        )

    except ET.ParseError as e:
        print(f"❌ 解析 XML 文件时出错: {e}")
        return None


def print_summary_report(report: CoverageReport) -> None:
    """打印摘要报告"""
    print("\n")
    print("=" * 70)
    print("📊 测试覆盖率统计报告")
    print("=" * 70)

    # 总体指标
    print("\n📈 总体指标")
    print("-" * 40)
    print(
        f"  代码行覆盖率: {report.line_rate*100:.2f}% "
        f"({report.total_lines_covered}/{report.total_lines} 行)",
    )
    print(
        f"  分支覆盖率:   {report.branch_rate*100:.2f}% "
        f"({report.total_branches_covered}/{report.total_branches} 分支)",
    )
    print(f"  文件/类数:    {report.file_count} 个")

    # 覆盖率分布
    dist = report.get_distribution()
    print("\n📊 覆盖率分布")
    print("-" * 40)
    print(f"  ✅ 优秀 (≥80%):    {dist['excellent']:3d} 个文件")
    print(f"  👍 良好 (60%-79%): {dist['good']:3d} 个文件")
    print(f"  ⚠️  中等 (40%-59%): {dist['medium']:3d} 个文件")
    print(f"  📉 较低 (20%-39%): {dist['low']:3d} 个文件")
    print(f"  ❌ 需改进 (<20%):  {dist['poor']:3d} 个文件")


def print_file_details(report: CoverageReport) -> None:
    """打印各文件详细覆盖率"""
    print("\n📁 各文件覆盖率详情")
    print("-" * 90)
    print(f"{'文件':<45} {'行覆盖率':>12} {'分支覆盖率':>12} {'状态':>12}")
    print("-" * 90)

    for f in report.files:
        line_pct = f"{f.line_rate*100:.1f}%"
        branch_pct = f"{f.branch_rate*100:.1f}%" if f.branches_total > 0 else "N/A"
        print(f"{f.name:<45} {line_pct:>12} {branch_pct:>12} {f.status:>12}")

    print("-" * 90)


def print_improvement_suggestions(report: CoverageReport) -> None:
    """打印改进建议"""
    # 找出覆盖率低于中等且代码量较大的文件
    coverage_threshold = COVERAGE_MEDIUM / 100  # 转换为小数
    low_coverage_files = [
        f
        for f in report.files
        if f.line_rate < coverage_threshold
        and f.lines_total > MIN_LINES_FOR_SUGGESTION
    ]
    low_coverage_files.sort(key=lambda f: -f.lines_total)

    if low_coverage_files:
        print("\n💡 改进建议 - 优先增加测试的文件")
        print("-" * 60)
        for i, f in enumerate(low_coverage_files[:10], 1):
            print(
                f"  {i}. {f.name} - {f.lines_total} 行, "
                f"{f.line_rate*100:.1f}% 覆盖率",
            )


def open_html_report(project_root: Path, output_dir: str) -> None:
    """在浏览器中打开 HTML 报告"""
    html_path = project_root / output_dir / "index.html"
    if not html_path.exists():
        print(f"❌ HTML 报告不存在: {html_path}")
        return

    print(f"\n🌐 在浏览器中打开报告: {html_path}")

    if platform.system() == "Darwin":
        subprocess.run(  # noqa: S603
            ["/usr/bin/open", str(html_path)],
            check=False,
        )
    elif platform.system() == "Windows":
        # Windows 下使用 webbrowser 模块更安全
        webbrowser.open(f"file://{html_path}")
    else:
        webbrowser.open(f"file://{html_path}")


def main() -> int:
    """主函数"""
    parser = argparse.ArgumentParser(
        description="生成项目测试覆盖率报告",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                  # 运行测试并生成报告
  %(prog)s --open           # 生成报告后在浏览器中打开
  %(prog)s --no-run         # 仅解析已有的 coverage.xml
  %(prog)s --output report  # 指定输出目录为 report/
        """,
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="生成报告后在浏览器中打开 HTML 报告",
    )
    parser.add_argument(
        "--no-run",
        action="store_true",
        help="跳过测试运行，仅解析已有的 coverage.xml",
    )
    parser.add_argument(
        "--output",
        default="coverage_report",
        help="报告输出目录（默认: coverage_report）",
    )
    parser.add_argument(
        "--brief",
        action="store_true",
        help="仅显示摘要，不显示文件详情",
    )

    args = parser.parse_args()

    project_root = get_project_root()
    print(f"📂 项目根目录: {project_root}")

    # 运行测试（除非指定 --no-run）
    if not args.no_run:
        success = run_tests_with_coverage(project_root, args.output)
        if not success:
            print("\n⚠️  部分测试失败，但仍会生成覆盖率报告")

    # 解析覆盖率数据
    print("\n📖 解析覆盖率数据...")
    report = parse_coverage_xml(project_root)

    if report is None:
        return 1

    # 打印报告
    print_summary_report(report)

    if not args.brief:
        print_file_details(report)

    print_improvement_suggestions(report)

    # 报告位置
    print("\n📁 生成的报告文件")
    print("-" * 40)
    print(f"  HTML 报告: {project_root / args.output / 'index.html'}")
    print(f"  XML 报告:  {project_root / 'coverage.xml'}")

    # 打开 HTML 报告
    if args.open:
        open_html_report(project_root, args.output)

    print("\n✅ 报告生成完成!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
