build ::
	python3 setup.py sdist

all ::
	python3 setup.py sdist bdist_wheel

deploy : all
	scp dist/* chablis:/usr/local/www/data/pip3/acsys/

clean ::
	find . -type f -name '*~' -delete
	for ii in $$(find . -type d -name __pycache__); do \
	  rm -rf $${ii}; \
	done
	rm -rf build dist __pycache__ acsys/acsys.egg-info .eggs
