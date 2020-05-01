acsys.tgz : LICENSE README.md setup.py acsys/*py
	tar czf $@ $^

clean ::
	find . -type f -name '*~' -delete
	for ii in $$(find . -type d -name __pycache__); do \
	  rm -rf $${ii}; \
	done
	rm -rf acsys.tgz __pycache__
