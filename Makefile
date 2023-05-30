test:
	echo working

freeze:
	-rm DT_GUI
	pyinstaller --onefile DT_GUI.py 
	-rm *.spec
	-rm -rf build
	mv dist/DT_GUI .
	-rm -rf dist

activate:
	conda activate guienv

run:
	python3 ./DT_GUI.py
