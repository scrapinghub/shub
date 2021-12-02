
start:
	echo "Hello World!"

requirements: requirements-test.txt

requirements-test.txt: requirements-test.in requirements.txt
	pip-compile -qU requirements-test.in

requirements.txt: setup.py
	pip-compile -qU setup.py

