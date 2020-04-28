acnet.tgz : LICENSE README.md setup.py acnet/*py
	tar czf $@ $^

clean ::
	find . -name \\*~ -delete
	rm -rf acnet.tgz __pycache__
