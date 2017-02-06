#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Author: Matthias Blum
# Contact: mat.blum@gmail.com

import config
import json
import os
import random
import re
import smtplib
import string
import time
from datetime import datetime

import MySQLdb
import tornado.escape
import tornado.ioloop
import tornado.options
import tornado.web


status_waiting = 0
status_queue = 1
status_sequencing = 2
status_sequenced = 3
status_archived = 4


class BaseHandler(tornado.web.RequestHandler):
    @property
    def uploads(self):
        return config.uploads_path

    @property
    def db(self):
        db = self.application.db
        try:
            con = MySQLdb.connect(db['host'], db['user'], db['password'], db['name'])
        except Exception, e:
            return None, None
        else:
            return con, con.cursor()

    def get_current_user(self):
        user_id = self.get_secure_cookie('spino')
        user = None

        con, cur = self.db
        if con:
            try:
                cur.execute('SELECT name, email, admin, creator, leader '
                            'FROM users '
                            'WHERE id=%s', (user_id, ))
                res = cur.fetchall()

                if res:
                    user = {
                        'id': int(user_id),
                        'name': res[0][0],
                        'email': res[0][1],
                        'admin': res[0][2],
                        'creator': res[0][3],
                        'leader': res[0][4]
                    }

                    # Update last connection
                    cur.execute('UPDATE users '
                                'SET last_connection = CURRENT_TIMESTAMP '
                                'WHERE id = %s', (user_id,))
            except:
                pass
            else:
                if user:
                    con.commit()
            finally:
                cur.close()
                con.close()
        else:
            user = False

        return user

    def get_user_files(self, user_id):
        files = []
        con, cur = self.db

        if con:
            try:
                cur.execute('SELECT id, name FROM files WHERE user_id = %s', (user_id,))
                res = cur.fetchall()
            except:
                pass
            else:
                for row in res:
                    # We added a timestamp for each file, but we do not want to show it to the users
                    filename = row[1].split('_')[1]
                    files.append([row[0], filename])
            finally:
                cur.close()
                con.close()
        return files

    def get_users(self):
        users = {}
        con, cur = self.db

        if con:
            try:
                cur.execute('SELECT id, name, email, admin, creator, leader, created, last_connection FROM users')
                res = cur.fetchall()
            except:
                pass
            else:
                for row in res:
                    users[int(row[0])] = {
                        'name': row[1],
                        'email': row[2],
                        'admin': row[3],
                        'creator': row[4],
                        'leader': row[5],
                        'created': row[6],
                        'last_connection': row[7]
                    }
            finally:
                cur.close()
                con.close()
        return users


class MainHandler(BaseHandler):
    def get(self):
        user = self.current_user

        if user:
            files = self.get_user_files(user['id'])

            if user['creator']:
                users = self.get_users()
            else:
                users = None

            self.render('index.html', user=user, files=files, users=users)
        elif user is None:  # None: not logged in or does not exist
            self.redirect('/signin')
        else:  # False: problem with database connection
            self.render('down.html')


class SignOutHandler(BaseHandler):
    def post(self):
        if self.current_user:
            self.clear_all_cookies()

        self.redirect('/')


class AdminHandler(BaseHandler):
    def get(self):
        user = self.current_user

        if user and user['admin']:
            self.render('admin.html', user=user, users=self.get_users(),
                        alert=None, email='', name='', passwd='', passwd2='')
        elif user:
            self.redirect('/')
        else:
            self.redirect('/signin')


class AdminPostHandler(BaseHandler):
    def post(self, action):
        user = self.current_user

        if user and user['admin']:
            alert = None
            users = self.get_users()

            if action == 'add':
                email = self.get_argument('email', '').lower()
                name = self.get_argument('name', '')
                passwd = self.get_argument('password', '')
                passwd2 = self.get_argument('password2', '')

                # All fields completed
                if not email or not name or passwd or not passwd2:
                    # Valid email address
                    if re.match(r"[^@]+@[^@]+\.[^@]+", email):
                        emails = [u['email'].lower() for k, u in users.items()]

                        if email not in emails:
                            # Password long enough
                            if len(passwd) >= 6:
                                # Verification matches password
                                if passwd == passwd2:
                                    is_creator = 1 if self.get_argument('is_creator', None) else 0
                                    is_leader = 1 if self.get_argument('is_leader', None) else 0
                                    is_admin = 1 if self.get_argument('is_admin', None) else 0

                                    con, cur = self.db
                                    if con:
                                        try:
                                            cur.execute('INSERT INTO users (name, email, password, admin, creator, leader) '
                                                        'VALUES (%s, %s, MD5(%s), %s, %s, %s)', (name, email, passwd,
                                                                                                 is_admin, is_creator,
                                                                                                 is_leader))
                                            new_id = cur.lastrowid
                                        except Exception, e:
                                            alert = ['danger', 'Something went wrong.']
                                        else:
                                            con.commit()
                                            users[new_id] = {
                                                'name': name,
                                                'email': email,
                                                'admin': is_admin,
                                                'creator': is_creator,
                                                'leader': is_leader,
                                                'created': '',
                                                'last_connection': ''
                                            }
                                            alert = ['success', 'Account successfully created.']
                                        finally:
                                            cur.close()
                                            con.close()
                                else:
                                    alert = ['warning', 'Passwords does not match.']
                            else:
                                alert = ['warning', 'Your password must be at least 6 characters long.']
                        else:
                            alert = ['danger', 'Email already taken.']
                    else:
                        alert = ['warning', 'Please enter a valid email address.']
                else:
                    alert = ['warning', 'Please complete all required fields.']

                self.render('admin.html', user=user, users=users, alert=alert, email=email, name=name, passwd=passwd, passwd2=passwd2)

            else:
                creators = self.get_uid_list(self.get_arguments('creator'))
                leaders = self.get_uid_list(self.get_arguments('leader'))
                admins = self.get_uid_list(self.get_arguments('admin'))

                set_creator = {}
                set_leader = {}
                set_admin = {}

                for uid in creators:
                    if uid in users and not users[uid]['creator']:
                        set_creator[uid] = 1

                for uid in leaders:
                    if uid in users and not users[uid]['leader']:
                        set_leader[uid] = 1

                for uid in admins:
                    if uid in users and not users[uid]['admin']:
                        set_admin[uid] = 1

                for uid, u in users.items():
                    if u['creator'] and uid not in creators:
                        set_creator[uid] = 0

                    if u['leader'] and uid not in leaders:
                        set_leader[uid] = 0

                    if u['admin'] and uid not in admins:
                        set_admin[uid] = 0

                if set_creator or set_leader or set_admin:
                    users_updated = False
                    con, cur = self.db
                    try:
                        for uid, val in set_creator.items():
                            cur.execute('UPDATE users SET creator=%s WHERE id=%s', (val, uid))

                        for uid, val in set_leader.items():
                            cur.execute('UPDATE users SET leader=%s WHERE id=%s', (val, uid))

                        for uid, val in set_admin.items():
                            cur.execute('UPDATE users SET admin=%s WHERE id=%s', (val, uid))
                    except:
                        alert = ['danger', 'Something went wrong.']
                    else:
                        con.commit()
                        users_updated = True
                    finally:
                        cur.close()
                        con.close()

                        if users_updated:
                            users = self.get_users()

                self.render('admin.html', user=user, users=users, alert=None, email='', name='', passwd='', passwd2='')
        elif user:
            self.redirect('/')
        else:
            self.redirect('/signin')

    def get_uid_list(self, lst):
        """
        Return an unique list of user ID
        :param lst:
        :return:
        """
        uid_lst = []

        for uid in lst:
            try:
                uid = int(uid)
            except:
                continue
            else:
                if uid not in uid_lst:
                    uid_lst.append(uid)

        return uid_lst


class AddSampleHandler(BaseHandler):
    def post(self):
        user = self.current_user

        if user:
            sample = {
                'antibody': self.get_argument('antibody', None),
                'application': self.get_argument('application', None),
                'barcode': self.get_argument('barcode', None),
                'cell_line': self.get_argument('cellline', None),
                'comment': self.get_argument('comment', None),
                'date': self.get_argument('date', None),
                'files': self.get_arguments('file'),
                'lane_usage': self.get_argument('laneusage', None),
                'organism': self.get_argument('organism', None),
                'owner': self.get_argument('ownerid', None),
                'platform_id': self.get_argument('platformid', None),
                'position': self.get_argument('position', None),
                'id': self.get_argument('sampleid', None),
                'time_point': self.get_argument('timepoint', None),
                'treatment': self.get_argument('treatment', None),
                'volume': self.get_argument('volume', None)
            }

            # A non-creator user cannot create a sample for someone else: they are the sample's owner
            # owner_id cannot be NULL so we set it to the creator ID, if they did not give any owner
            if not user['creator'] or not sample['owner']:
                sample['owner'] = user['id']

            # Look for a missing field
            valid = True
            for k, v in sample.items():
                if not v:
                    if k == 'comment':
                        sample[k] = None
                    elif k == 'files':
                        valid = False  # Even for "creator" users, a file is required
                        break
                    elif not user['creator']:
                        valid = False
                    else:
                        sample[k] = None

            if valid:
                con, cur = self.db

                if con:
                    try:
                        # The "nice" id (DDMMYY-X) is unique: check if it is not already taken
                        id_exists = False
                        if sample['id']:
                            sample['id'] = sample['id'].upper()
                            cur.execute('SELECT COUNT(*) FROM samples WHERE sample_id = %s', (sample['id'],))
                            res = cur.fetchall()

                            if res[0][0]:
                                id_exists = True

                        if not id_exists:
                            # Keep unique files only
                            files = []
                            for f in sorted(sample['files']):
                                if f not in files:
                                    files.append(f)

                            fields = ['sample_id', 'platform_id', 'owner_id',
                                      'status', 'date', 'position',
                                      'lane_usage', 'barcode', 'volume',
                                      'application', 'organism', 'cell_line',
                                      'treatment', 'time_point', 'antibody',
                                      'comment', 'creator_id']

                            values = [sample['id'], sample['platform_id'], sample['owner'],
                                      status_waiting, sample['date'], sample['position'],
                                      sample['lane_usage'], sample['barcode'], sample['volume'],
                                      sample['application'], sample['organism'], sample['cell_line'],
                                      sample['treatment'], sample['time_point'], sample['antibody'],
                                      sample['comment'], user['id']]

                            sql_query = ('INSERT INTO samples (%s) '
                                         'VALUES (%s)' % (','.join(fields),
                                                          ','.join(['%s' for i in range(len(values))])))

                            cur.execute(sql_query, tuple(values))

                            # Get the just inserted sample ID
                            last_id = cur.lastrowid

                            # Insert relations sample - report(s)
                            for f in files:
                                cur.execute('INSERT INTO relations (sample_id, report_id) '
                                            'VALUES (%s, %s)', (last_id, f))
                    except Exception, e:
                        self.write(json.dumps({
                            'code': 1,
                            'class': 'alert-danger',
                            'html': "<strong>Heck!</strong> Something went wrong. Contact Spino's administrator."
                        }))
                    else:
                        con.commit()

                        if id_exists:
                            self.write(json.dumps({
                                'code': 1,
                                'class': 'alert-danger',
                                'html': '<strong>Oh snap!</strong> The sample %s already exists.' % sample['id']
                            }))
                        else:
                            self.write(json.dumps({
                                'code': 0,
                                'class': 'alert-success',
                                'html': '<strong>Well done!</strong> Sample successfully added.'
                            }))
                    finally:
                        cur.close()
                        con.close()
            else:
                self.write(json.dumps({
                    'code': 1,
                    'class': 'alert-danger',
                    'html': '<strong>Hey!</strong> Please complete all required fields.'
                }))
        else:
            self.redirect('/signin')


class DeleteSampleHandler(BaseHandler):
    def post(self):
        user = self.current_user

        # Need to be logged in to delete a sample
        if user:
            sample_id = self.get_argument('id')
            con, cur = self.db

            if con:
                # Verify if the sample exists and belongs to the user (either owner or creator)
                try:
                    cur.execute('SELECT count(*) '
                                'FROM samples '
                                'WHERE id=%s AND (creator_id=%s OR owner_id=%s)', (sample_id, user['id'], user['id']))
                    res = cur.fetchone()
                except:
                    self.write('1')
                else:
                    if res[0]:
                        # Exists and belongs: we delete it
                        try:
                            cur.execute('DELETE FROM samples WHERE id=%s', (sample_id,))
                        except:
                            self.write('1')
                        else:
                            con.commit()
                            self.write('0')
                finally:
                    cur.close()
                    con.close()
        else:
            self.redirect('/signin')


class EditSampleHandler(BaseHandler):
    def post(self):
        user = self.current_user

        if user:
            sample = {
                'antibody': self.get_argument('antibody', None),
                'application': self.get_argument('application', None),
                'barcode': self.get_argument('barcode', None),
                'cell_line': self.get_argument('cellline', None),
                'comment': self.get_argument('comment', None),
                'date': self.get_argument('date', None),
                'files': self.get_arguments('file'),
                'id': self.get_argument('realid'),
                'lane_usage': self.get_argument('laneusage', None),
                'organism': self.get_argument('organism', None),
                'owner_id': self.get_argument('ownerid', None),
                'platform_id': self.get_argument('platformid', None),
                'position': self.get_argument('position', None),
                'sample_id': self.get_argument('sampleid', None),
                'time_point': self.get_argument('timepoint', None),
                'treatment': self.get_argument('treatment', None),
                'volume': self.get_argument('volume', None)
            }

            # A non-creator user cannot create a sample for someone else: they are the sample's owner
            if not user['creator']:
                sample['owner'] = user['id']

            # Look for a missing field
            valid = True
            for k, v in sample.items():
                if not v:
                    if k == 'comment':
                        sample[k] = None
                    elif k == 'files':
                        valid = False  # Even for "creator" users, a file is required
                        break
                    elif not user['creator']:
                        # If not a creator, they could not set the owner (they are) so it would be None
                        if k == 'owner_id':
                            sample[k] = user['id']
                        else:
                            valid = False
                            break
                    else:
                        sample[k] = None
                elif k == 'sample_id':
                    sample[k] = v.upper()

            if valid:
                con, cur = self.db

                if con:
                    try:
                        # Verify if the sample exists and if the current user has the right to edit it
                        cur.execute('SELECT s.sample_id, s.platform_id, s.owner_id, s.date, s.position, s.lane_usage, '
                                    's.barcode, s.volume, s.application, s.organism, s.cell_line, s.treatment, '
                                    's.time_point, s.antibody, s.comment, GROUP_CONCAT(r.report_id) AS files '
                                    'FROM samples s '
                                    'INNER JOIN relations r '
                                    'ON r.sample_id = s.id '
                                    'WHERE id=%s AND (owner_id=%s OR creator_id=%s)', (sample['id'], user['id'], user['id']))
                        res = cur.fetchall()
                        desc = cur.description
                    except:
                        self.write(json.dumps({
                            'code': 1,
                            'class': 'alert-danger',
                            'html': "<strong>Heck!</strong> Something went wrong. Contact Spino's administrator."
                        }))
                    else:
                        # We found the sample with that ID and it belongs (owned by or created by) to the current user
                        if res:
                            files_to_insert = []
                            files_to_delete = []
                            fields_to_update = []
                            values_to_update = []
                            for (name, value) in zip(desc, res[0]):
                                field = name[0]

                                # MySQL concat with commas, so we split the files' ID by commas
                                if field == 'files':
                                    old_files = value.split(',')
                                    new_files = sample[name[0]]

                                    # Find the now useless relations sample-file
                                    for f in old_files:
                                        if f not in new_files and f not in files_to_delete:
                                            files_to_delete.append(f)

                                    # Find the new relations sample-file
                                    for f in new_files:
                                        if f not in old_files and f not in files_to_insert:
                                            files_to_insert.append(f)

                                # Compare as strings since date, volume, and time_point are datetime/long from mysql
                                # and unicode from the client (too lazy to cast them)
                                elif str(value) != str(sample[field]):
                                    # Force the owner id to the user id (owner id cannot be null in DB)
                                    if field == 'owner_id' and not sample[field]:
                                        sample[field] = user['id']

                                    fields_to_update.append(field)
                                    values_to_update.append(sample[field])

                            try:
                                # Since the sample ID is unique, we need to check if the new one is not already taken
                                sample_id_free = True
                                if 'sample_id' in fields_to_update:
                                    idx = fields_to_update.index('sample_id')
                                    cur.execute('SELECT count(*) FROM samples WHERE sample_id=%s', (values_to_update[idx],))
                                    res = cur.fetchone()

                                    if res[0]:
                                        sample_id_free = False
                            except:
                                self.write(json.dumps({
                                    'code': 1,
                                    'class': 'alert-danger',
                                    'html': "<strong>Heck!</strong> Something went wrong. Contact Spino's administrator."
                                }))
                            else:
                                # Either their is no sample id (creator's case) or it is free
                                if sample_id_free:
                                    try:
                                        # Update sample with new values
                                        if fields_to_update:
                                            set_statement = ','.join(['%s=%%s' % i for i in fields_to_update])

                                            sql_update = 'UPDATE samples SET %s WHERE id=%s' % (set_statement, sample['id'])
                                            cur.execute(sql_update, tuple(values_to_update))

                                        # Update sample with new relations
                                        for f in files_to_insert:
                                            cur.execute('INSERT INTO relations (sample_id, report_id) '
                                                        'VALUES (%s, %s)', (sample['id'], f))

                                        # Update sample by deleting old relations
                                        for f in files_to_delete:
                                            cur.execute('DELETE FROM relations '
                                                        'WHERE sample_id=%s AND report_id=%s', (sample['id'], f))
                                    except:
                                        self.write(json.dumps({
                                            'code': 1,
                                            'class': 'alert-danger',
                                            'html': "<strong>Heck!</strong> Something went wrong."
                                                    "Contact Spino's administrator."
                                        }))
                                    else:
                                        con.commit()
                                        self.write(json.dumps({
                                            'code': 0
                                        }))
                                else:
                                    self.write(json.dumps({
                                        'code': 1,
                                        'class': 'alert-danger',
                                        'html': '<strong>Oh snap!</strong> '
                                                'The sample %s already exists.' % values_to_update[idx]
                                    }))
                        else:
                            self.write(json.dumps({
                                'code': 1,
                                'class': 'alert-danger',
                                'html': '<strong>You cannot edit this sample.</strong>'
                            }))
                    finally:
                        cur.close()
                        con.close()
            else:
                self.write(json.dumps({
                    'code': 1,
                    'class': 'alert-danger',
                    'html': '<strong>Please complete all required fields.</strong>'
                }))

        else:
            self.redirect('/signin')


class GetSamplesHandler(BaseHandler):
    def post(self):
        user = self.current_user

        if user:
            draw = int(self.get_argument('draw'))
            start = int(self.get_argument('start'))
            length = int(self.get_argument('length'))
            search = self.get_argument('search[value]', '').lower()
            order_dir = self.get_argument('order[0][dir]')
            order_col = self.get_argument('order[0][column]')
            col_name = self.get_argument('columns[%s][name]' % order_col)
            col_orderable = self.get_argument('columns[%s][orderable]' % order_col)

            # Filtering only if three characters at least
            if len(search) < 3:
                search = ''

            # self.request.arguments <- all passed arguments

            sql_query = ('SELECT DISTINCT s.id, s.sample_id, s.platform_id, s.position, s.date, '
                         's.lane_usage, s.barcode, s.volume, s.application, s.organism, '
                         's.cell_line, s.treatment, s.time_point, s.antibody, s.comment, '
                         's.status, s.owner_id, s.creator_id, u1.name as owner, u2.name as creator, '
                         'GROUP_CONCAT(f.id) AS report_id, GROUP_CONCAT(f.name) AS report '
                         'FROM samples s '
                         'INNER JOIN users u1 ON u1.id = s.owner_id '
                         'INNER JOIN users u2 ON u2.id = s.creator_id '
                         'INNER JOIN relations r ON r.sample_id = s.id '
                         'INNER JOIN files f ON f.id = r.report_id '
                         'GROUP BY s.id')

            if col_orderable == 'true':  # We're dealing with javascript, here
                # Orderable columns
                cols_dict = {
                    'sampleid': 's.sample_id',
                    'platformid': 's.platform_id',
                    'users': 'owner',
                    'application': 's.application',
                    'organism': 's.organism',
                    'celline': 's.cell_line',
                    'antibody': 's.antibody',
                    'date': 's.date'
                }

                if col_name in cols_dict:
                    order_dir = 'ASC' if order_dir == 'asc' else 'DESC'
                    sql_query += ' ORDER BY %s %s' % (cols_dict[col_name], order_dir)

            data = []
            res = []
            con, cur = self.db

            if con:
                con.set_character_set('utf8')
                try:
                    cur.execute(sql_query)
                    res = cur.fetchall()
                except Exception, e:
                    print e
                else:
                    for row in res:
                        add_row = False
                        if search:
                            # Search in sample ID, platform ID, application, organism, cell line, antibody, users
                            for e in (row[1], row[2], row[8], row[9], row[10], row[13], row[18], row[19]):
                                if e and search in e.lower():
                                    add_row = True
                                    break
                        else:
                            add_row = True

                        if add_row:
                            files = []

                            # Split on comma because MySQL concat with commas
                            for fid, fname in zip(row[20].split(','), row[21].split(',')):
                                files.append([fid, fname])

                            entry = {
                                'sampleid': row[1],
                                'platformid': row[2],
                                'position': row[3],
                                'date': str(row[4]) if row[4] else None,
                                'laneusage': row[5],
                                'barcode': row[6],
                                'volume': row[7],
                                'application': row[8],
                                'organism': row[9],
                                'cellline': row[10],
                                'treatment': row[11],
                                'timepoint': row[12],
                                'antibody': row[13],
                                'comment': row[14],
                                'status': row[15],
                                'ownerid': int(row[16]),
                                'creatorid': int(row[17]),
                                'users': [row[18], row[19]],  # user, creator
                                'files': files
                            }

                            edit = False  # Current user can edit the sample
                            changestatus = False  # Current user can change the sample's status

                            if user['id'] == entry['ownerid'] or user['id'] == entry['creatorid']:
                                edit = True

                                if entry['status'] != status_waiting:
                                    # Sample already approved
                                    changestatus = True

                            if user['leader']:
                                changestatus = True

                            entry['edit'] = edit
                            entry['id'] = [row[0], changestatus]  # Sample ID, change status ability
                            data.append(entry)
                finally:
                    cur.close()
                    con.close()

                    self.write(json.dumps({
                        'draw': draw,
                        'recordsTotal': len(res),
                        'recordsFiltered': len(data),
                        'data': data[start:start+length]
                    }))
        else:
            self.redirect('/signin')


class SignInHandler(BaseHandler):
    def get(self):
        if self.current_user:
            self.redirect('/')
        else:
            self.render('signin.html', alert=None, email='', passwd=None)

    def post(self):
        email = tornado.escape.utf8(self.get_argument('email'))
        password = tornado.escape.utf8(self.get_argument('password'))

        if email and password:
            con, cur = self.db

            if con:
                try:
                    cur.execute('SELECT id, name, email FROM users WHERE email=%s AND password=MD5(%s)', (email, password))
                    res = cur.fetchall()
                except:
                    self.render('signin.html', alert=True, email=email)
                else:
                    if len(res):
                        self.set_secure_cookie('spino', str(res[0][0]))
                        self.redirect('/')
                    else:
                        self.render('signin.html', alert=True, email=email)
            else:
                self.render('down.html')
        else:
            self.render('signin.html', alert=True, email=email)


class UploadHandler(BaseHandler):
    def post(self):
        user = self.current_user

        if user:
            if self.request.files:
                inputfile = self.request.files['inputfile'][0]

                # Used for not having two files with the same name
                timestamp = int(time.time())

                # MySQL uses commas when concatenating: remove them, otherwise a file could be considered as two
                filename = inputfile['filename'].replace(',', '')
                filename = '%s_%s' % (timestamp, filename)

                dest = os.path.join(self.uploads, filename)
                with open(dest, 'w') as fo:
                    fo.write(inputfile['body'])

                con, cur = self.db

                if con:
                    try:
                        cur.execute('INSERT INTO files (name, user_id) '
                                    'VALUES (%s, %s)', (filename, user['id']))
                    except Exception, e:
                        os.unlink(dest)
                    else:
                        con.commit()
                    finally:
                        cur.close()
                        con.close()
                        self.redirect('/')
            else:
                self.redirect('/')
        else:
            self.redirect('/signin')


class AccountHandler(BaseHandler):
    def get(self):
        user = self.current_user

        if user:
            files = self.get_files(user['id'])

            self.render('account.html', alert=None, user=user, files=files, passwd='', passwd2='')
        else:
            self.redirect('/signin')

    def post(self):
        user = self.current_user

        if user:
            files = self.get_files(user['id'])

            files_to_delete = self.get_arguments('file')
            password = self.get_argument('password', '')
            password2 = self.get_argument('password2', '')

            alert = None

            # Check for new password's length and verification
            update_passwd = None
            if password:
                # Six characters min
                if len(password) >= 6:
                    # Verification
                    if password == password2:
                        update_passwd = password
                    else:
                        alert = {
                            'class': 'alert-warning',
                            'title': 'Oh, hamburgers!',
                            'text': 'Passwords does not match.'
                        }
                else:
                    alert = {
                        'class': 'alert-warning',
                        'title': 'Oh, shizzle!',
                        'text': 'Your password must be at least 6 characters long.'
                    }

            to_delete_owned = {}
            if files_to_delete:
                # Dictionary of files owned by the current user and that can be deleted non linked to any sample
                files_dict = {}
                for f in files:
                    if not f[4]:
                        # File not linked to a sample
                        files_dict[f[0]] = f[1]

                for f_id in files_to_delete:
                    try:
                        f_id = int(f_id)
                    except:
                        pass
                    else:
                        if f_id in files_dict:
                            to_delete_owned[f_id] = files_dict[f_id]

            if to_delete_owned or update_passwd:
                con, cur = self.db

                if con:
                    try:
                        if update_passwd:
                            cur.execute('UPDATE users SET password = MD5(%s) '
                                        'WHERE id = %s', (password, user['id']))

                        if to_delete_owned:
                            for f in to_delete_owned:
                                cur.execute('DELETE FROM files WHERE id=%s', (f,))

                            # Update the list of the user's file (remove the just deleted)
                            files = [f for f in files if f[0] not in to_delete_owned]
                    except:
                        alert = {
                            'class': 'alert-danger',
                            'title': 'Uh, oh!',
                            'text': 'Something went wrong.'
                        }
                    else:
                        con.commit()

                        for f_id, f_name in to_delete_owned.items():
                            os.unlink(os.path.join(config.uploads_path, f_name))

                        if update_passwd:
                            alert = {
                                'class': 'alert-success',
                                'title': 'Bravo!',
                                'text': 'You password was successfully changed.'
                            }
                    finally:
                        cur.close()
                        con.close()

            self.render('account.html', alert=alert, user=user, files=files, passwd=password, passwd2=password2)
        else:
            self.redirect('/signin')

    def get_files(self, user_id):

        files = []
        con, cur = self.db

        if con:
            try:
                cur.execute('SELECT f.id, f.name, GROUP_CONCAT(r.sample_id) '
                            'FROM files f '
                            'LEFT JOIN relations r ON f.id = r.report_id '
                            'WHERE f.user_id = %s '
                            'GROUP BY f.id', (user_id,))
                res = cur.fetchall()
            except:
                pass
            else:
                for row in res:
                    ts_name = row[1].split('_')
                    f_date = datetime.fromtimestamp(int(ts_name[0])).strftime('%Y-%m-%d %H:%M')

                    # Id, local name, name, date, used
                    files.append([int(row[0]), row[1], ts_name[1], f_date, row[2]])
            finally:
                cur.close()
                con.close()

        return files


class SamplesStatusHandler(BaseHandler):
    def post(self):
        samples = self.get_arguments('id')
        new_status = self.get_argument('status', None)

        if new_status:
            # Status must be a number
            try:
                new_status = int(new_status)
            except:
                pass
            else:
                # Unique list of number (samples' ID)
                sample_id = []
                for i in samples:
                    try:
                        i = int(i)
                    except:
                        continue
                    else:
                        if i not in sample_id:
                            sample_id.append(i)

                if sample_id:
                    user = self.current_user

                    if user:
                        if not user['leader']:
                            sql = ('SELECT id, status, owner_id, creator_id '
                                   'FROM samples '
                                   'WHERE id IN (%s)' % ','.join(['%s' for i in sample_id]))
                            user_samples = []  # Samples that belong to the user (with the right to change the status)
                            con, cur = self.db

                            if con:
                                try:
                                    cur.execute(sql, tuple(sample_id))
                                    res = cur.fetchall()
                                except:
                                    pass
                                else:
                                    for row in res:
                                        # Common users can change a sample's status if it is not waiting for approval
                                        # and if they own the sample (either creator or owner)
                                        # If the sample has already the new status, we do not update it
                                        if row[1] != 0 and (user['id'] == row[2] or user['id'] == row[3]) and row[1] != new_status:
                                            user_samples.append(row[0])
                                    sample_id = user_samples
                                finally:
                                    cur.close()
                                    con.close()

                        if sample_id:
                            con, cur = self.db

                            if con:
                                try:
                                    for sid in sample_id:
                                        cur.execute('UPDATE samples SET status=%s WHERE id=%s', (new_status, sid))
                                except:
                                    pass
                                else:
                                    con.commit()
                                finally:
                                    cur.close()
                                    con.close()
                                    self.write('0')


class ResetPasswordHandler(BaseHandler):
    def get(self):
        self.render('password_reset.html', alert=None)

    def post(self):
        email = self.get_argument('email', '').strip()
        alert = None

        if email:
            con, cur = self.db

            if con:
                try:
                    cur.execute('SELECT id FROM users WHERE email=%s', (email, ))
                    res = cur.fetchone()
                except:
                    pass
                else:
                    if res:
                        user_id = res[0]

                        chars = string.ascii_letters + string.digits
                        new_password = ''.join(random.choice(chars) for _ in range(10))

                        from_addr = 'admin@spino'
                        to_addr_lst = [email]
                        header = 'From: %s\n' % from_addr
                        header += 'To: %s\n' % ','.join(to_addr_lst)
                        header += 'Subject: [Spino] Password reset\n\n'
                        message = ("Your Spino password has been reset!\n"
                                   "Your new password is: %s.\n"
                                   "Don't forget to change it once you're logged in.\n\n"
                                   "Thanks." % new_password)
                        message = header + message

                        try:
                            server = smtplib.SMTP('smtp.gmail.com:587')
                            server.starttls()
                            server.login('ngs.qc.team@gmail.com', 'gronemeyer-ngs-qc')
                            problems = server.sendmail(from_addr, to_addr_lst, message)
                            server.quit()

                            cur.execute('UPDATE users SET password=MD5(%s) WHERE id=%s', (new_password, user_id))
                        except:
                            alert = 'danger'
                        else:
                            if problems:
                                print problems
                                alert = 'danger'
                            else:
                                con.commit()
                                alert = 'success'
                    else:
                        alert = 'danger'

                finally:
                    cur.close()
                    con.close()
        else:
            alert = 'danger'

        self.render('password_reset.html', alert=alert)




class Application(tornado.web.Application):
    def __init__(self):
        """
        generate cookie_secret:
            import uuid
            print str(uuid.uuid4())

        or
            import base64, uuid
            print base64.b64encode(uuid.uuid4().bytes + uuid.uuid4().bytes)
        """
        if not os.path.isdir(config.uploads_path):
            print "No such file or directory: '%s'" % config.uploads_path
            exit(1)

        self.db = {
            'host': tornado.options.options.dbhost,
            'name': tornado.options.options.dbname,
            'user': tornado.options.options.dbuser,
            'password': tornado.options.options.dbpasswd,
            'port': tornado.options.options.port
        }

        settings = {
            'static_path': os.path.join(os.path.dirname(__file__), 'static'),
            'template_path': os.path.join(os.path.dirname(__file__), 'templates'),
            'cookie_secret': '57883cd0-59fc-4018-9284-377a4e4f0ba0'
        }

        handlers = [
            (r'/', MainHandler),
            (r'/account', AccountHandler),
            (r'/admin', AdminHandler),
            (r'/admin/(add|manage)', AdminPostHandler),
            (r'/signin', SignInHandler),
            (r'/signout', SignOutHandler),
            (r'/samples/add', AddSampleHandler),
            (r'/samples/delete', DeleteSampleHandler),
            (r'/samples/edit', EditSampleHandler),
            (r'/samples/get', GetSamplesHandler),
            (r'/samples/status', SamplesStatusHandler),
            (r'/password_reset', ResetPasswordHandler),
            (r'/upload', UploadHandler),
            (r'/files/(.*)', tornado.web.StaticFileHandler, dict(path=config.uploads_path))
        ]

        # Starting Application
        tornado.web.Application.__init__(self, handlers, debug=tornado.options.options.debug, **settings)


def main():
    tornado.options.define('debug', default=False, help='Debug', type=bool)
    tornado.options.define('port', default=6666, help='Port used by Tornado', type=int)
    tornado.options.define('dbhost', default='localhost', help='Database host', type=str)
    tornado.options.define('dbname', help='Database name', type=str)
    tornado.options.define('dbuser', help='Database user', type=str)
    tornado.options.define('dbpasswd', help='Database password', type=str)
    tornado.options.parse_command_line()
    application = Application()
    application.listen(tornado.options.options.port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()