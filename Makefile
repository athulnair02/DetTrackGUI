test:
	echo working

freeze:
	-rm DT_GUI
	pyinstaller DT_GUI.py --onefile
	-rm *.spec
	-rm -rf build
	mv dist/DT_GUI .
	-rm -rf dist

activate:
	conda activate guienv

run:
	python3 ./DT_GUI.py
