"""Metrics Visualizer - Tạo biểu đồ từ dữ liệu logs và reports."""

import re
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Sử dụng backend không cần GUI
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MetricsVisualizer:
    """Visualize metrics từ logs và reports."""
    
    def __init__(self, logs_dir: str = "logs", reports_dir: str = "reports", output_dir: str = "utils"):
        """Khởi tạo visualizer.
        
        Args:
            logs_dir: Thư mục chứa logs
            reports_dir: Thư mục chứa reports
            output_dir: Thư mục lưu ảnh (mặc định: utils)
        """
        # Lấy thư mục gốc của ai_engine
        base_dir = Path(__file__).parent.parent
        
        self.logs_dir = base_dir / logs_dir
        self.reports_dir = base_dir / reports_dir
        self.output_dir = base_dir / output_dir
        
        # Tạo output directory nếu chưa tồn tại
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"📂 Logs dir: {self.logs_dir}")
        logger.info(f"📂 Reports dir: {self.reports_dir}")
        logger.info(f"📂 Output dir: {self.output_dir}")
    
    def parse_crawl_reports(self) -> List[Dict[str, Any]]:
        """Parse các crawl reports và gom theo ngày."""
        daily_data = {}
        
        if not self.reports_dir.exists():
            logger.warning(f"Reports directory không tồn tại: {self.reports_dir}")
            return []
        
        for report_file in self.reports_dir.glob("crawl_report_*.txt"):
            try:
                content = report_file.read_text(encoding='utf-8')
                
                # Parse thông tin
                date_match = re.search(r'Date\s+:\s+(.+)', content)
                total_books_match = re.search(r'Total Books\s+:\s+(\d+)', content)
                api_requests_match = re.search(r'API Requests\s+:\s+(\d+)', content)
                errors_match = re.search(r'Errors\s+:\s+(\d+)', content)
                
                if all([date_match, total_books_match]):
                    # Lấy ngày (bỏ giờ)
                    date_str = date_match.group(1).strip()[:10]
                    
                    # Gom dữ liệu theo ngày
                    if date_str not in daily_data:
                        daily_data[date_str] = {
                            'date': date_str,
                            'total_books': 0,
                            'api_requests': 0,
                            'errors': 0,
                            'runs': 0
                        }
                    
                    daily_data[date_str]['total_books'] += int(total_books_match.group(1))
                    daily_data[date_str]['api_requests'] += int(api_requests_match.group(1)) if api_requests_match else 0
                    daily_data[date_str]['errors'] += int(errors_match.group(1)) if errors_match else 0
                    daily_data[date_str]['runs'] += 1
                    
            except Exception as e:
                logger.error(f"Lỗi khi parse {report_file.name}: {e}")
        
        # Chuyển về list và sắp xếp theo ngày
        return sorted(daily_data.values(), key=lambda x: x['date'])
    
    def parse_processor_reports(self) -> List[Dict[str, Any]]:
        """Parse các processor reports và gom theo ngày."""
        daily_data = {}
        
        if not self.reports_dir.exists():
            logger.warning(f"Reports directory không tồn tại: {self.reports_dir}")
            return []
        
        for report_file in self.reports_dir.glob("processor_report_*.txt"):
            try:
                content = report_file.read_text(encoding='utf-8')
                
                # Parse thông tin
                date_match = re.search(r'Date\s+:\s+(.+)', content)
                total_match = re.search(r'TOTAL RAW INPUT\s+:\s+(\d+)', content)
                valid_match = re.search(r'VALID BOOKS \(KEPT\)\s+:\s+(\d+)', content)
                duplicate_match = re.search(r'Duplicate ID\s+:\s+(\d+)', content)
                no_desc_match = re.search(r'No Description\s+:\s+(\d+)', content)
                no_identifier_match = re.search(r'No Identifier\s+:\s+(\d+)', content)
                no_thumbnail_match = re.search(r'No Thumbnail\s+:\s+(\d+)', content)
                
                if all([date_match, total_match, valid_match]):
                    # Lấy ngày (bỏ giờ)
                    date_str = date_match.group(1).strip()[:10]
                    
                    # Gom dữ liệu theo ngày
                    if date_str not in daily_data:
                        daily_data[date_str] = {
                            'date': date_str,
                            'total_input': 0,
                            'valid_books': 0,
                            'duplicates': 0,
                            'no_description': 0,
                            'no_identifier': 0,
                            'no_thumbnail': 0,
                            'runs': 0
                        }
                    
                    daily_data[date_str]['total_input'] += int(total_match.group(1))
                    daily_data[date_str]['valid_books'] += int(valid_match.group(1))
                    daily_data[date_str]['duplicates'] += int(duplicate_match.group(1)) if duplicate_match else 0
                    daily_data[date_str]['no_description'] += int(no_desc_match.group(1)) if no_desc_match else 0
                    daily_data[date_str]['no_identifier'] += int(no_identifier_match.group(1)) if no_identifier_match else 0
                    daily_data[date_str]['no_thumbnail'] += int(no_thumbnail_match.group(1)) if no_thumbnail_match else 0
                    daily_data[date_str]['runs'] += 1
                    
            except Exception as e:
                logger.error(f"Lỗi khi parse {report_file.name}: {e}")
        
        # Chuyển về list và sắp xếp theo ngày
        return sorted(daily_data.values(), key=lambda x: x['date'])
    
    def parse_process_logs(self) -> Dict[str, int]:
        """Parse process logs để lấy số lượng sách theo topic."""
        topic_stats = {}
        
        if not self.logs_dir.exists():
            logger.warning(f"Logs directory không tồn tại: {self.logs_dir}")
            return topic_stats
        
        for log_file in self.logs_dir.glob("process_*.log"):
            try:
                content = log_file.read_text(encoding='utf-8')
                
                # Parse từng dòng để tìm topic và số sách
                for line in content.split('\n'):
                    match = re.search(r'Processing: raw_(.+?)_\d{8}_\d{6}_\d+\.json', line)
                    books_match = re.search(r'Processed (\d+) valid books', line)
                    
                    if match and books_match:
                        topic = match.group(1).replace('_', ' ')
                        num_books = int(books_match.group(1))
                        
                        if topic not in topic_stats:
                            topic_stats[topic] = 0
                        topic_stats[topic] += num_books
            except Exception as e:
                logger.error(f"Lỗi khi parse {log_file.name}: {e}")
        
        return topic_stats
    
    def load_books_data(self) -> List[Dict[str, Any]]:
        """Load dữ liệu sách từ file processed JSON."""
        base_dir = Path(__file__).parent.parent
        data_dir = base_dir / "data" / "processed"
        
        if not data_dir.exists():
            logger.warning(f"Data directory không tồn tại: {data_dir}")
            return []
        
        # Tìm file JSON mới nhất
        json_files = list(data_dir.glob("clean_books_*.json"))
        if not json_files:
            logger.warning("Không tìm thấy file clean_books JSON")
            return []
        
        latest_file = max(json_files, key=lambda f: f.stat().st_mtime)
        
        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"✅ Đã load {len(data)} sách từ {latest_file.name}")
            return data
        except Exception as e:
            logger.error(f"Lỗi khi load {latest_file.name}: {e}")
            return []
    
    def create_aggregate_summary_chart(self, crawl_data: List[Dict[str, Any]], processor_data: List[Dict[str, Any]], books_data: List[Dict[str, Any]]):
        """Tạo biểu đồ tổng quan aggregate (gộp tất cả ngày)."""
        if not processor_data:
            logger.warning("Không có dữ liệu processor để visualize")
            return
        
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        fig.suptitle('TỔNG QUAN XỬ LÝ DỮ LIỆU', fontsize=16, fontweight='bold')
        
        # Calculate aggregates FROM PROCESSOR REPORT (primary source)
        total_crawled = sum([d['total_input'] for d in processor_data]) if processor_data else 0
        total_valid = sum([d['valid_books'] for d in processor_data]) if processor_data else 0
        
        # Dropped items details (ALL types from processor report)
        total_duplicates = sum([d['duplicates'] for d in processor_data]) if processor_data else 0
        total_no_desc = sum([d['no_description'] for d in processor_data]) if processor_data else 0
        total_no_identifier = sum([d.get('no_identifier', 0) for d in processor_data]) if processor_data else 0
        total_no_thumbnail = sum([d.get('no_thumbnail', 0) for d in processor_data]) if processor_data else 0
        
        # Chart 1: Total Crawled vs Valid Books
        categories = ['Tổng số sách\nđã thu thập', 'Sách hợp lệ\nđã giữ lại']
        values = [total_crawled, total_valid]
        colors = ['#3498db', '#2ecc71']
        
        bars = axes[0].bar(categories, values, color=colors, alpha=0.7, width=0.5)
        axes[0].set_title('Tổng số sách: Thu thập vs Hợp lệ', fontweight='bold', fontsize=14)
        axes[0].set_ylabel('Số lượng sách', fontweight='bold')
        axes[0].grid(axis='y', alpha=0.3)
        
        # Add value labels
        for bar, val in zip(bars, values):
            height = bar.get_height()
            axes[0].text(bar.get_x() + bar.get_width()/2., height + 1,
                        f'{int(val):,}', ha='center', va='bottom', fontweight='bold', fontsize=12)
        
        # Chart 2: Dropped Items (ALL types with details)
        drop_categories = ['Trùng lặp', 'Thiếu\nmô tả', 'Thiếu\nID', 'Thiếu\nảnh bìa']
        drop_values = [total_duplicates, total_no_desc, total_no_identifier, total_no_thumbnail]
        drop_colors = ['#e67e22', '#e74c3c', '#9b59b6', '#95a5a6']
        
        bars2 = axes[1].bar(drop_categories, drop_values, color=drop_colors, alpha=0.7, width=0.5)
        axes[1].set_title('Sách bị loại bỏ (Tất cả loại)', fontweight='bold', fontsize=14)
        axes[1].set_ylabel('Số lượng', fontweight='bold')
        axes[1].grid(axis='y', alpha=0.3)
        
        for bar, val in zip(bars2, drop_values):
            if val > 0:
                height = bar.get_height()
                axes[1].text(bar.get_x() + bar.get_width()/2., height + 2, 
                            f'{int(val):,}', ha='center', va='bottom', fontweight='bold', fontsize=10)
        
        plt.tight_layout()
        
        # Lưu file
        output_path = self.output_dir / f"aggregate_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"✅ Đã lưu biểu đồ: {output_path}")
        
        plt.show()
        plt.close()
    
    def create_language_category_stats(self, books_data: List[Dict[str, Any]]):
        """Tạo biểu đồ thống kê ngôn ngữ."""
        if not books_data:
            logger.warning("Không có dữ liệu sách để phân tích")
            return
        
        fig, ax = plt.subplots(1, 1, figsize=(10, 8))
        fig.suptitle('PHÂN BỐ NGÔN NGỮ', fontsize=16, fontweight='bold')
        
        # Count languages
        language_count = {'Tiếng Anh': 0, 'Tiếng Việt': 0, 'Khác': 0}
        for book in books_data:
            lang = book.get('language', 'en')
            if lang == 'vi':
                language_count['Tiếng Việt'] += 1
            elif lang == 'en':
                language_count['Tiếng Anh'] += 1
            else:
                language_count['Khác'] += 1
        
        # Trừ 1 cho mỗi loại ngôn ngữ theo yêu cầu
        for lang in language_count:
            if language_count[lang] > 0:
                language_count[lang] -= 1
        
        # Language Distribution PIE CHART with counts
        lang_labels_with_counts = []
        lang_values = []
        for k, v in language_count.items():
            if v > 0:
                lang_labels_with_counts.append(f'{k}\n({v} sách)')
                lang_values.append(v)
        
        lang_colors = ['#3498db', '#e74c3c', '#95a5a6'][:len(lang_labels_with_counts)]
        
        wedges, texts, autotexts = ax.pie(lang_values, labels=lang_labels_with_counts, autopct='%1.1f%%',
                                            colors=lang_colors, startangle=90, textprops={'fontsize': 12})
        ax.set_title('Phân bổ ngôn ngữ', fontweight='bold', fontsize=14, pad=20)
        
        for text in texts:
            text.set_fontsize(12)
            text.set_fontweight('bold')
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
            autotext.set_fontsize(13)
        
        plt.tight_layout()
        
        # Lưu file
        output_path = self.output_dir / f"language_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"✅ Đã lưu biểu đồ: {output_path}")
        
        plt.show()
        plt.close()
    
    def create_topic_distribution_chart(self, topic_stats: Dict[str, int]):
        """Tạo biểu đồ phân bố sách theo topic."""
        if not topic_stats:
            logger.warning("Không có dữ liệu topic để visualize")
            return
        
        # Sắp xếp theo số lượng
        sorted_topics = sorted(topic_stats.items(), key=lambda x: x[1], reverse=True)
        topics = [t[0] for t in sorted_topics[:15]]  # Top 15
        counts = [t[1] for t in sorted_topics[:15]]
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
        fig.suptitle('PHÂN BỐ SÁCH THEO CHỦ ĐỀ', fontsize=16, fontweight='bold')
        
        # Chart 1: Bar chart
        colors = plt.cm.viridis(np.linspace(0, 1, len(topics)))
        bars = ax1.barh(range(len(topics)), counts, color=colors, alpha=0.8)
        ax1.set_yticks(range(len(topics)))
        ax1.set_yticklabels(topics, fontsize=9)
        ax1.set_xlabel('Số lượng sách', fontweight='bold')
        ax1.set_title('Top 15 chủ đề theo số lượng sách', fontweight='bold')
        ax1.grid(axis='x', alpha=0.3)
        
        # Thêm số vào bar
        for i, (bar, count) in enumerate(zip(bars, counts)):
            ax1.text(count + 0.5, i, str(count), va='center', fontweight='bold')
        
        # Chart 2: Pie chart (top 10)
        top_10_topics = topics[:10]
        top_10_counts = counts[:10]
        
        colors_pie = plt.cm.Set3(np.linspace(0, 1, len(top_10_topics)))
        wedges, texts, autotexts = ax2.pie(top_10_counts, labels=top_10_topics, autopct='%1.1f%%',
                                             colors=colors_pie, startangle=90)
        ax2.set_title('Phân bố Top 10 chủ đề', fontweight='bold')
        
        # Style cho text
        for text in texts:
            text.set_fontsize(8)
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
            autotext.set_fontsize(8)
        
        plt.tight_layout()
        
        # Lưu file
        output_path = self.output_dir / f"topic_distribution_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"✅ Đã lưu biểu đồ: {output_path}")
        
        # Hiển thị
        plt.show()
        plt.close()
    
    def create_book_fields_analysis(self, books_data: List[Dict[str, Any]]):
        """Tạo biểu đồ phân tích các trường thông tin sách."""
        if not books_data:
            logger.warning("Không có dữ liệu sách để phân tích")
            return
        
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        fig.suptitle('PHÂN TÍCH TRƯỜNG DỮ LIỆU SÁCH', fontsize=16, fontweight='bold')
        
        # Publication Decade with Counts instead of percentages
        years = []
        for book in books_data:
            year = book.get('publish_year', 'Unknown')
            if year and year != 'Unknown':
                try:
                    year_int = int(re.search(r'\d{4}', str(year)).group())
                    if 1900 <= year_int <= 2030:
                        years.append(year_int)
                except:
                    pass
        
        if years:
            year_counts = {}
            for year in years:
                decade = (year // 10) * 10
                year_counts[decade] = year_counts.get(decade, 0) + 1
            
            sorted_decades = sorted(year_counts.items())
            decades_labels = [f"{d}s" for d, _ in sorted_decades]
            decade_counts = [c for _, c in sorted_decades]
            
            colors = plt.cm.viridis(np.linspace(0, 1, len(decades_labels)))
            ax.bar(range(len(decades_labels)), decade_counts, color=colors, alpha=0.7)
            ax.set_title('Sách theo thập kỷ xuất bản (Số lượng)', fontweight='bold', fontsize=14)
            ax.set_xlabel('Thập kỷ', fontweight='bold')
            ax.set_ylabel('Số lượng sách', fontweight='bold')
            ax.set_xticks(range(len(decades_labels)))
            ax.set_xticklabels(decades_labels, rotation=45)
            ax.grid(axis='y', alpha=0.3)
            
            for i, count in enumerate(decade_counts):
                ax.text(i, count + 0.5, str(count), ha='center', fontweight='bold')
        
        plt.tight_layout()
        
        # Lưu file
        output_path = self.output_dir / f"book_fields_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"✅ Đã lưu biểu đồ: {output_path}")
        
        # Hiển thị
        plt.show()
        plt.close()
    
    def create_categories_analysis(self, books_data: List[Dict[str, Any]]):
        """Tạo biểu đồ phân tích categories (hiển thị tất cả)."""
        if not books_data:
            logger.warning("Không có dữ liệu sách để phân tích categories")
            return
        
        # Thu thập categories (from 'category' field in JSON)
        categories_dict = {}
        for book in books_data:
            category = book.get('category', '')
            if category and category != 'Unknown':
                # Split by comma if multiple categories
                cats = [c.strip() for c in category.split(',') if c.strip() and c.strip() != 'Unknown']
                for cat in cats:
                    categories_dict[cat] = categories_dict.get(cat, 0) + 1
        
        if not categories_dict:
            logger.warning("Không có dữ liệu categories")
            return
        
        # Sắp xếp và hiển thị TẤT CẢ categories
        sorted_cats = sorted(categories_dict.items(), key=lambda x: x[1], reverse=True)
        
        fig, ax = plt.subplots(1, 1, figsize=(14, max(8, len(sorted_cats) * 0.4)))
        fig.suptitle('PHÂN BỐ TẤT CẢ THỂ LOẠI', fontsize=16, fontweight='bold')
        
        # Hiển thị tất cả categories
        cat_names = [c[0][:40] for c in sorted_cats]  # Cắt tên dài
        cat_counts = [c[1] for c in sorted_cats]
        
        colors = plt.cm.tab20c(np.linspace(0, 1, len(cat_names)))
        bars = ax.barh(range(len(cat_names)), cat_counts, color=colors, alpha=0.8)
        ax.set_yticks(range(len(cat_names)))
        ax.set_yticklabels(cat_names, fontsize=9)
        ax.set_xlabel('Số lượng sách', fontweight='bold')
        ax.set_title(f'Tất cả {len(cat_names)} thể loại', fontweight='bold', fontsize=14)
        ax.grid(axis='x', alpha=0.3)
        
        for i, count in enumerate(cat_counts):
            ax.text(count + 0.3, i, str(count), va='center', fontsize=8, fontweight='bold')
        
        plt.tight_layout()
        
        # Lưu file
        output_path = self.output_dir / f"all_categories_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"✅ Đã lưu biểu đồ: {output_path}")
        
        plt.show()
        plt.close()
        plt.close()
    
    def generate_all_charts(self):
        """Tạo tất cả các biểu đồ."""
        logger.info("🚀 Bắt đầu tạo biểu đồ metrics...")
        
        # Parse dữ liệu
        crawl_data = self.parse_crawl_reports()
        processor_data = self.parse_processor_reports()
        topic_stats = self.parse_process_logs()
        books_data = self.load_books_data()
        
        # Tạo biểu đồ aggregate summary
        if crawl_data or processor_data:
            logger.info(f"📊 Tạo biểu đồ aggregate summary...")
            self.create_aggregate_summary_chart(crawl_data, processor_data, books_data)
        
        # Tạo biểu đồ language/category stats
        if books_data:
            logger.info(f"📊 Tạo biểu đồ language & category stats ({len(books_data)} books)...")
            self.create_language_category_stats(books_data)
        
        if topic_stats:
            logger.info(f"📊 Tạo biểu đồ topic distribution ({len(topic_stats)} topics)...")
            self.create_topic_distribution_chart(topic_stats)
        
        # Tạo biểu đồ phân tích sách
        if books_data:
            logger.info(f"📊 Tạo biểu đồ phân tích fields ({len(books_data)} books)...")
            self.create_book_fields_analysis(books_data)
            
            logger.info(f"📊 Tạo biểu đồ categories (all categories)...")
            self.create_categories_analysis(books_data)
        
        logger.info("✨ Hoàn thành tất cả biểu đồ!")
        logger.info(f"📁 Các ảnh đã được lưu tại: {self.output_dir}")


def main():
    """Main function để chạy visualizer."""
    visualizer = MetricsVisualizer()
    visualizer.generate_all_charts()


if __name__ == "__main__":
    main()
