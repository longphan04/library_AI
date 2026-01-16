# MySQL Integration Module

## Structure

```
src/mysql/
├── __init__.py
├── data_inserter.py    # Class insert data vào MySQL
└── sync_data.py        # Script sync từ JSON → MySQL
```

## Usage

### **Import DataInserter**

```python
from src.mysql.data_inserter import DataInserter

inserter = DataInserter()
inserter.insert_book(processed_data)
inserter.close()
```

### **Run Sync**

```bash
# Via main.py
python main.py sync-to-mysql

# Direct
python -m src.mysql.sync_data
```

## Features

- **Auto-create**: Publishers, categories, authors
- **Deduplication**: Check ISBN before insert
- **N-N linking**: book_categories, book_authors
- **Shelf assignment**: Based on category
- **Statistics**: Track insertions

## Files

### **data_inserter.py**
Core class với methods:
- `insert_book()` - Main insertion logic
- `_get_or_create_publisher()` - Publisher lookup/create
- `_get_or_create_category()` - Category lookup/create
- `_get_or_create_author()` - Author lookup/create
- `_assign_shelf()` - Shelf assignment logic

### **sync_data.py**
Script để sync tất cả processed JSON files vào MySQL.