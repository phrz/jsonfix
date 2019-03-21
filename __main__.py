import fileinput
from .jsonfix import Fixer

if __name__ == '__main__':
	total_input = ''
	for line in fileinput.input():
		total_input += line
	
	fixer = Fixer()
	out = fixer.fix(total_input)
	print(out)
