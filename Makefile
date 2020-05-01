acsys.tgz : LICENSE README.md setup.py acsys/*py
	tar czf $@ $^

clean ::
	find . -name \\*~ -delete
	rm -rf acsys.tgz __pycache__
