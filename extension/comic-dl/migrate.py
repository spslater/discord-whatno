#!/usr/bin/env python3

from tinydb import TinyDB, where
from datetime import datetime
import sqlite3
import re

def createTables(db : sqlite3.Cursor):
	 db.executescript("""
			CREATE TABLE Arc(
				number PRIMARY KEY,
				name TEXT UNIQUE NOT NULL,
				url TEXT UNIQUE NOT NULL
			);

			CREATE TABLE Comic(
				release PRIMARY KEY,
				title TEXT NOT NULL,
				image TEXT UNIQUE NOT NULL,
				url TEXT UNIQUE NOT NULL,
				arcId
						REFERENCES Arc(rowid)
						ON DELETE CASCADE
						ON UPDATE CASCADE
						NOT NULL
			);

			CREATE TABLE Alt(
				comicId
						UNIQUE
						REFERENCES Comic(release)
						ON DELETE CASCADE
						ON UPDATE CASCADE
						NOT NULL,
				alt TEXT NOT NULL
			);

			CREATE TABLE Tag(
				comicId
						REFERENCES Comic(release)
						ON DELETE CASCADE
						ON UPDATE CASCADE
						NOT NULL,
				tag TEXT NOT NULL
			);
	 """)

def addArc(db, img):
	data = img.split('_')
	num = data[1]
	name = data[2]
	url =	'https://www.dumbingofage.com/category/comic/book-' + (num[1] if num[0] == '0' else num) + '/' + num[2:3] + '-' + name + '/'
	
	db.execute('SELECT * FROM Arc WHERE number=?', (num,))	
	row = db.fetchone()

	if not row:
		db.execute('INSERT INTO Arc VALUES (?,?,?)', (num, name, url))
		db.execute('SELECT * FROM Arc WHERE number=?', (num,))	
		row = db.fetchone()

	return row

def addComic(db, img, arc):
	titleRelease = img.split('_')[3]
	title = '.'.join('-'.join(titleRelease.split('-')[3:]).split('.')[:-1])
	release = '-'.join(titleRelease.split('-')[0:3])
	url = re.sub('category', release[0:4], arc[2], count=1) + title + '/'

	db.execute('SELECT * FROM Comic WHERE release=?', (release,))
	row = db.fetchone()

	if not row:
		try:
			db.execute('INSERT INTO Comic VALUES (?,?,?,?,?)', (release, title, img, url, arc[0]))
		except:
			url = url[:-2] + '-2' + url[-1]
			db.execute('INSERT INTO Comic VALUES (?,?,?,?,?)', (release, title, img, url, arc[0]))
		db.execute('SELECT * FROM Comic WHERE release=?', (release,))	
		row = db.fetchone()

	return row

def addAlt(db, comic, alt):
	db.execute('SELECT * FROM Alt WHERE comicId=?', (comic[0],))	
	row = db.fetchone()

	if not row:
		db.execute('INSERT INTO Alt VALUES (?,?)', (comic[0], alt))
		db.execute('SELECT * FROM Alt WHERE comicId=?', (comic[0],))	
		row = db.fetchone()

	return row

def addTag(db, comic, tag):
	db.execute('SELECT * FROM Tag WHERE comicId=? AND tag=?', (comic[0], tag))	
	row = db.fetchone()

	if not row:
		db.execute('INSERT INTO Tag VALUES (?,?)', (comic[0], tag))
		db.execute('SELECT * FROM Tag WHERE comicId=? AND tag=?', (comic[0], tag))	
		row = db.fetchone()

	return row


def main():
	conn = sqlite3.connect('dumbingofage.db')
	db = conn.cursor()

	createTables(db)

	tdb = TinyDB('DumbingOfAge.db')
	tAlt = tdb.table('alts')
	tTag = tdb.table('tags')

	'''
		def addArc(db, img):
		def addComic(db, img, arc):
		def addCharacter(db, char):
		def addAlt(db, comic, alt):
		def addTag(db, comic, tag):
	'''

	# {"img": "DumbingOfAge_1004_is-a-song-forever_2020-07-11-thewarners.png", "alt": "there i s anot h e r  s k y w a l k e  r"},
	for alt in tAlt.all():
		print(alt)
		print('\tarc')
		arc = addArc(db, alt['img'])
		print('\tcomic')
		comic = addComic(db, alt['img'], arc)
		print('\talt')
		altRow = addAlt(db, comic, alt['alt'])
		print('\t' + str(altRow))

	# {"img": "DumbingOfAge_1004_is-a-song-forever_2020-07-16-tonedeaf.png", "tag": "becky"}
	for tag in tTag.all():
		print(tag)
		print('\tarc')
		arc = addArc(db, tag['img'])
		print('\tcomic')
		comic = addComic(db, tag['img'], arc)
		print('\ttag')
		tagRow = addTag(db, comic, tag['tag'])
		print('\t' + str(tagRow))

	conn.commit()
	conn.close()

if __name__ == "__main__":
	main()
