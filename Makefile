.PHONY: all db analytics data pages scholars validate

all: db analytics data scholars pages validate

db:
	python build_and_populate_db.py

analytics:
	python generate_analytics.py

data:
	python generate_site_data.py

scholars:
	python generate_scholars_pages.py

pages:
	python generate_publication_pages.py

validate:
	python validate_publication.py

clean:
	python -c "import pathlib; [p.unlink() for p in pathlib.Path('.').glob('site_data_timeline_*.json')]; [p.unlink() for p in pathlib.Path('p').glob('*.html') if p.is_file()]; [p.unlink() for p in pathlib.Path('s').glob('*.html') if p.is_file()]; [p.unlink() for p in pathlib.Path('themes').glob('*.html') if p.name != 'index.html']"

