'''
Adapted from github.com/adhocore/php-json-fixer
> © Jitendra Adhikari <jiten.adhikary@gmail.com>
>   <https://github.com/adhocore>
>   Licensed under MIT license.

Python adaptation by Paul Herz (github.com/phrz)
'''

# Tested to work on Python 3.7.2
#
# Usage: python3 -m jsonfix file.json
#        cat file.json | python3 -m jsonfix -

from typing import List, Optional, Dict, Tuple, Callable
import json
from collections import OrderedDict
import re

whitespace = {' ', '\t', '\r', '\n'}

# e.g. split_at(lambda x: x < 0, [1, 2, 3, -1, -2, -3]) => ([1,2,3], [-1,-2,-3])
def split_at(predicate: Callable[[str], bool], l: str, from_right=False) -> Tuple[str, str]:
	split_i = None
	r = range(len(l))
	if from_right:
		r = reversed(r)
	for i in r:
		if predicate(l[i]):
			return (l[:i], l[i:])
	return (l, '')

class Fixer:
	# Current token stack indexed by position
	_token_stack: OrderedDict = OrderedDict()

	# If current char is within a string
	_is_in_string: bool = False

	_complementary_pairs: Dict[str, str] = {
		'{': '}',
		'[': ']',
		'"': '"'
	}
	
	# the last seen '{' position
	_last_object_position: Optional[int] = -1

	# the last seen '[' position
	_last_array_position: Optional[int] = -1

	# the value to use for missing strings (can be null, true, false)
	_missing_value: str = 'null'

	# raises RuntimeError if fixing fails.
	# returns fixed json string.
	def fix(self, json_string: str) -> str:
		head, body, tail = self._trim(json_string)

		if len(body) == 0 or self._is_valid_json(body):
			return body

		quick_fixed_json = self._quick_fix(body)
		if quick_fixed_json is not None:
			return quick_fixed_json

		self._reset()

		l = len(body)

		for i in range(l):
			char = body[i]
			prev = '' if i == 0 else body[i-1]
			next = '' if i+1 >= l else body[i+1]
			
			if char not in whitespace:
				self._stack(prev, char, i, next)

		return head + self._fix_or_fail(body) + tail
	
	def _trim(self, string: str) -> Tuple[str, str, str]:
		# we preserve leading and trailing whitespace to reconstruct
		# whitespace for user convenience (and readability!)
		leading, body_and_trailing = split_at(lambda c: c not in whitespace, string)
		body, trailing = split_at(lambda c: c in whitespace, body_and_trailing, from_right=True)
		return (leading, body, trailing)

	def _is_valid_json(self, json_string: str) -> bool:
		try:
			json.loads(json_string)
			return True
		except json.JSONDecodeError:
			return False

	def _quick_fix(self, json_string: str) -> Optional[str]:
		pair = self._complementary_pairs.get(json_string[0])
		if len(json_string) == 1 and pair is not None:
			return json_string + pair
		elif json_string[0] != '"':
			return self._maybe_literal(json_string)

		return self._pad_string(json_string)

	def _reset(self):
		self._token_stack = OrderedDict()
		self._is_in_string = False
		self._last_object_position = -1
		self._last_array_position = -1

	# attempt to complete truncated JSON literals (true, false, null)
	def _maybe_literal(self, json_string: str) -> Optional[str]:
		if json_string[0] not in {'t', 'f', 'n'}:
			return None

		for literal in ['true', 'false', 'null']:
			if json_string.startswith(literal):
				return literal

		return None

	def _stack(self, prev: str, char: str, i: int, next: str):
		if self._maybe_string(prev, char, i):
			return

		last = self._last_token()

		if last is not None and last in ',:"' and char in '"0123456789{[tfn':
			self._pop_token()

		if char in ',:[{':
			self._token_stack[i] = char

		self._update_position(char, i)

	def _last_token(self) -> Optional[str]:
		if len(self._token_stack):
			last_key = list(self._token_stack.keys())[-1]
			return self._token_stack[last_key]
		else:
			return None

	def _pop_token(self, token: Optional[str] = None) -> Optional[str]:
		if token is None:
			return self._token_stack.popitem()

		keys = reversed(self._token_stack.keys())
		for key in keys:
			if self._token_stack[key] == token:
				del self._token_stack[key]
				break

		return None

	def _maybe_string(self, prev: str, char: str, i: int) -> bool:
		# this char is an unescaped quote
		if prev != '\\' and char == '"':
			self._is_in_string = not self._is_in_string
		if self._is_in_string and self._last_token() != '"':
			self._token_stack[i] = '"'
		return self._is_in_string

	def _update_position(self, char: str, i: int):
		if char == '{':
			self._last_object_position = i;
		elif char == '}':
			self._pop_token('{')
			self._last_object_position = -1
		elif char == '[':
			self._last_array_position = i
		elif char == ']':
			self._pop_token('[')
			self._last_array_position = -1

	def _fix_or_fail(self, json_string: str) -> str:
		l = len(json_string)
		tmp = self._pad(json_string)

		if self._is_valid_json(tmp):
			return tmp

		raise RuntimeError(f'Could not fix JSON (tried padding "{tmp[l:]}")')

	def _pad(self, tmp_json: str) -> str:
		if not self._is_in_string:
			tmp_json = tmp_json.rstrip(',')
			while self._last_token() == ',':
				self._pop_token()

		tmp_json = self._pad_literal(tmp_json)
		tmp_json = self._pad_object(tmp_json)

		return self._pad_stack(tmp_json)

	def _pad_literal(self, tmp_json: str) -> str:
		if self._is_in_string:
			return tmp_json

		match = re.match(r'(tr?u?e?|fa?l?s?e|nu?l?l?)$', tmp_json)

		if match is None:
			# this may be malformed
			return tmp_json

		g1 = match.group(1)
		literal = self._maybe_literal(g1)
		if not match or literal is None:
			return tmp_json

		return tmp_json[:0-len(g1)] + literal

	def _pad_stack(self, tmp_json: str) -> str:
		# by accounting for all of the levels of nesting on the stack,
		# i.e. how many arrays, objects, and strings deep we are,
		# close out all of those levels of nesting with the complementary
		# close token "}" "]" or double quote
		for key, token in reversed(self._token_stack.items()):
			pair = self._complementary_pairs.get(token)
			if pair is not None:
				tmp_json += pair
		return tmp_json

	def _pad_object(self, tmp_json: str) -> str:
		if not self._object_needs_padding(tmp_json):
			return tmp_json

		part = tmp_json[self._last_object_position + 1:]

		# if the contents of the json segment match a
		# well-formed object's contents (keys and values,
		# comma delimited, with colons, etc.)
		if re.match(r'(\s*\"[^"]+\"\s*:\s*[^,]+,?)+$', part):
			return tmp_json

		if self._is_in_string:
			tmp_json += '"'

		if not tmp_json.endswith(':'):
			tmp_json += ':'

		tmp_json += self._missing_value

		if self._last_token() == '"':
			self._pop_token()

		return tmp_json

	def _object_needs_padding(self, tmp_json: str) -> bool:
		last = tmp_json[-1]
		is_empty = last == '{' and not self._is_in_string
		return not is_empty and self._last_array_position < self._last_object_position

	def _pad_string(self, string: str) -> Optional[str]:
		last = string[-1]
		last2 = string[-2:]
		if last2 == '\\"' or last != '"':
			return string + '"'

		return None
