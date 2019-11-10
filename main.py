# -*- coding: utf-8 -*-

import json
import logging
import re
import warnings
from time import time
from urllib import urlencode
from urllib2 import urlopen
from zlib import adler32

import urllib3.contrib.appengine
import vk_api
from google.appengine.ext import ndb

import webapp2
from requests_toolbelt.adapters import appengine

from config import TGBOTUSERNAME, TGBOTTOKEN
from config import VKAPIVER, VKTOKEN, VKGROUPTOKEN, VKMYID, TIMETRESHOLD
from config import confirmation, wallpost, comment, tg2vkid

TGAPIURL = 'https://api.telegram.org/bot'
VKWALLURL = 'https://vk.com/wall-'
VKAPIURL = 'https://api.vk.com/method/'

appengine.monkeypatch()
warnings.filterwarnings('ignore', r'urllib3 is using URLFetch', urllib3.contrib.appengine.AppEnginePlatformWarning)

class Message(ndb.Model):
    tgmsgid = ndb.IntegerProperty()
    vkmsgid = ndb.IntegerProperty()
    tgchatid = ndb.IntegerProperty()
    vkchatid = ndb.IntegerProperty()
    timestamp = ndb.IntegerProperty()
    checksum = ndb.IntegerProperty(default=1)

class vkUser(ndb.Model):
    name = ndb.StringProperty()

def trimReply(text, length):
    if len(text) > length:
        return text[:length] + '...'
    return text

def tgMsg(msg, chatid, token=TGBOTTOKEN, disable_preview='false', reply_to=0):
    response = urlopen(TGAPIURL + token + '/sendMessage', urlencode({
        'chat_id': chatid,
        'text': msg.encode('utf-8'),
        'disable_web_page_preview': disable_preview,
        'parse_mode': 'HTML',
        'reply_to_message_id': reply_to
    })).read()
    return json.loads(response)

def tgEditMsg(chatid, msgid, text, token=TGBOTTOKEN):
    response = urlopen(TGAPIURL + token + '/editMessageText', urlencode({
        'chat_id': chatid,
        'message_id': msgid,
        'text': text.encode('utf-8'),
        'parse_mode': 'HTML'
    })).read()
    return json.loads(response)

def tgPhoto(url, caption, chatid, token=TGBOTTOKEN):
    response = urlopen(TGAPIURL + token + '/sendPhoto', urlencode({
        'chat_id': chatid,
        'photo': url,
        'caption': caption.encode('utf-8'),
        'parse_mode': 'HTML',
    })).read()
    return json.loads(response)

def tgLocation(lat, lon, chatid, token=TGBOTTOKEN, reply_to=0):
    response = urlopen(TGAPIURL + token + '/sendLocation', urlencode({
        'chat_id': chatid,
        'latitude': lat,
        'longitude': lon,
        'reply_to_message_id': reply_to
    })).read()
    return json.loads(response)

def tgGetFile(fileid):
    resp = json.loads(urlopen(TGAPIURL + TGBOTTOKEN + '/getFile', urlencode({'file_id': fileid})).read())
    if resp['ok']:
        return 'https://api.telegram.org/file/bot' + TGBOTTOKEN + '/' + resp['result']['file_path']
    return ""

def getVkName(userid):
    vkuser = vkUser.get_or_insert(str(userid))
    if vkuser.name:
        return vkuser.name
    else:
        resp = json.loads(urlopen(VKAPIURL+'users.get?access_token='+VKTOKEN+'&v='+VKAPIVER+'&lang=ru&user_ids='+str(userid)).read())['response']
        if resp:
            vkname = resp[0]['first_name'] + " " + resp[0]['last_name']
        else:
            resp = json.loads(urlopen(VKAPIURL+'groups.getById?access_token='+VKTOKEN+'&v='+VKAPIVER+'&group_ids='+str(abs(userid))).read())['response']
            if resp:
                vkname = resp[0]['name']
            else:
                vkname = 'Unknown'
        vkuser.name = vkname
        vkuser.put()
        return vkname

def getVkPhotoUrl(attachment):
    maxsize = 0
    for size in attachment['photo']['sizes']:
        if size['width'] > maxsize:
            maxsize = size['width']
            url = size['url']
    return url

def getVkStickerUrl(attachment):
    maxsize = 0
    for size in attachment['sticker']['images']:
        if size['width'] > maxsize:
            maxsize = size['width']
            url = size['url']
    return url

def getReplyText(message):
    reply = message.get('reply_to_message')
    replytext = ''

    if reply:
        replytext = reply.get('text', '')
        replycaption = reply.get('caption')
        replyfrom = reply['from']

        if reply.get('photo'):
            replytext = '[photo]'
        if reply.get('document'):
            replytext = '[file]'
        if reply.get('video'):
            replytext = '[video]'
        if reply.get('audio'):
            replytext = '[audio]'
        if reply.get('location'):
            replytext = '[location]'
        if reply.get('contact'):
            replytext = '[contact] ' + reply.get('contact')['first_name'] + ' ' + reply.get('contact')['phone_number']
        if reply.get('sticker'):
            replytext = reply.get('sticker').get('emoji', '[sticker]')
        if replycaption:
            replytext = replytext + ' ' + replycaption
        if replyfrom.get('username') == TGBOTUSERNAME:
            replyname = ''
        else:
            replyname = getTgName(replyfrom) + ': '
        replytext = u'\u23e9 ' + replyname + trimReply(replytext, 40) + u' \u23ea\n'

    return replytext


def cleanUnicode(inputString):
    return re.sub(u'[\u0300-\u036F]', '', inputString, 0)

def getTgName(msgfrom):
    first_name = msgfrom.get('first_name')
    last_name = msgfrom.get('last_name')
    if last_name is None:
        name = first_name
    else:
        name = first_name + " " + last_name
    return cleanUnicode(name)

def findReplyID(post, vkchatid, vk2tgid):
    reply_to = 0
    if 'reply_message' in post:
        vkreplyid = post['reply_message']['conversation_message_id']
        vkreplyfrom = post['reply_message']['from_id']
        vkreplyname = getVkName(vkreplyfrom)
        vkreplytime = post['reply_message']['date']
        vkreplytext = post['reply_message']['text']

        # trying to find by message id
        dbmsgs = Message.query(Message.vkmsgid == vkreplyid, Message.vkchatid == vkchatid, Message.tgchatid == vk2tgid[vkchatid]).fetch(1)
        for dbmsg in dbmsgs:
            reply_to = dbmsg.tgmsgid
            vkreplychecksum = adler32(vkreplytext.encode('utf-8'))
            if vkreplychecksum != dbmsg.checksum:
                # message edited
                tgEditMsg(chatid=vk2tgid[vkchatid], msgid=reply_to, text='<b>' + vkreplyname + ':</b> ' + vkreplytext)
                dbmsg.checksum = vkreplychecksum
                dbmsg.put()

        # trying to find by timestamp and checksum
        if reply_to == 0:
            vkreplychecksum = adler32(vkreplytext.encode('utf-8'))
            dbmsgs = Message.query(ndb.AND(Message.vkchatid == vkchatid, Message.tgchatid == vk2tgid[vkchatid], Message.checksum == vkreplychecksum, ndb.OR(Message.timestamp == vkreplytime, Message.timestamp == vkreplytime + TIMETRESHOLD))).fetch()
            for dbmsg in dbmsgs:
                reply_to = dbmsg.tgmsgid
                dbmsg.vkmsgid = vkreplyid
                dbmsg.put()

    return reply_to

def vkProcessForwards(post, boldnamec, vk2tgid, vkchatid, text):
    for fwdmsg in post.get('fwd_messages'):
        fwdfrom = fwdmsg['from_id']
        fwdname = getVkName(fwdfrom)
        fwdtext = fwdmsg['text']
        if fwdtext != '':
            tgMsg(msg=boldnamec + '[forward] ' + fwdname + ': ' + fwdtext, chatid=vk2tgid[vkchatid])

        for attachment in fwdmsg['attachments']:
            if attachment['type'] == 'photo':
                tgPhoto(url=getVkPhotoUrl(attachment), caption=boldnamec + u'[forward] Фото от ' + fwdname, chatid=vk2tgid[vkchatid])
            elif attachment['type'] == 'sticker':
                tgPhoto(url=getVkStickerUrl(attachment), caption=boldnamec + u'[forward] Стикер от ' + fwdname, chatid=vk2tgid[vkchatid])
            elif attachment['type'] == 'link':
                if text == '':
                    tgMsg(msg=boldnamec + '[forward] ' + fwdname + ': ' + attachment['link']['url'], chatid=vk2tgid[vkchatid])
            elif attachment['type'] == 'wall':
                tgMsg(msg=boldnamec + '[forward] ' + fwdname + ': https://vk.com/wall' + str(attachment['wall']['from_id']) + '_' + str(attachment['wall']['id']), chatid=vk2tgid[vkchatid])
            else:
                tgMsg(msg=boldnamec + '[forward] ' + fwdname + ': [' + attachment['type'] + ']', chatid=vk2tgid[vkchatid])


class vkHandler(webapp2.RequestHandler):
    def post(self):
        body = json.loads(self.request.body)
        logging.info(json.dumps(body, indent=4).decode('unicode-escape'))

        groupid = body['group_id']

        # webhook confirmation
        if body['type'] == 'confirmation' and groupid in confirmation:
            self.response.write(confirmation[groupid])
            return

        post = body['object']
        vkchatid = post.get('peer_id')
        text = post.get('text')
        postid = str(post.get('id'))
        parentid = str(post.get('post_id'))
        fromid = post.get('from_id')
        createdby = post.get('created_by')
        geo = post.get('geo')

        name = getVkName(fromid)
        boldname = '<b>' + name + '</b>'
        boldnamec = '<b>' + name + ':</b> '

        vk2tgid = {}
        for tgchatid in tg2vkid:
            vk2tgid[2000000000 + tg2vkid[tgchatid]] = tgchatid

        if text:
            text = re.sub(r'(\[(id|club)\d+\|(.+?)\])', r'\3', text)

        # wall post
        if body['type'] == 'wall_post_new':
            if createdby == VKMYID and u'\U0001f479' in text:
                pass
            else:
                groupname = getVkName(post['owner_id'])
                nmcreatedby = getVkName(createdby)
                msg = '<b>' + groupname + ' / ' + nmcreatedby + '</b>\n' + text + '\n' + VKWALLURL + str(groupid) + '_' + postid
                if 'attachments' in post and post['attachments'][0]['type'] == 'photo':
                    photoUrl = getVkPhotoUrl(post['attachments'][0])
                    if photoUrl != '':
                        if len(msg) <= 1024:
                            tgPhoto(url=photoUrl, caption=msg, chatid=wallpost[groupid])
                        else:
                            tgPhoto(url=photoUrl, caption='', chatid=wallpost[groupid])
                            tgMsg(msg=msg, chatid=wallpost[groupid], disable_preview='true')
                    else:
                        tgMsg(msg=msg, chatid=wallpost[groupid], disable_preview='true')
                else:
                    tgMsg(msg=msg, chatid=wallpost[groupid], disable_preview='true')

        # comment
        if body['type'] == 'wall_reply_new' or body['type'] == 'photo_comment_new':
            commenturl = VKWALLURL + str(groupid) + '_' + parentid + '?reply=' + postid
            if text:
                tgMsg(msg=boldnamec + text + '\n' + commenturl, chatid=comment[groupid], disable_preview='true')
            for attachment in post.get('attachments', []):
                if attachment['type'] == 'photo':
                    tgPhoto(url=getVkPhotoUrl(attachment), caption=boldname + '\n' + commenturl, chatid=comment[groupid])
                elif attachment['type'] == 'sticker':
                    tgPhoto(url=getVkStickerUrl(attachment), caption=boldname + '\n' + commenturl, chatid=comment[groupid])
                elif attachment['type'] == 'link':
                    tgMsg(msg=boldnamec + attachment['link']['url'] + '\n' + commenturl, chatid=comment[groupid])
                elif attachment['type'] == 'wall':
                    tgMsg(msg=boldnamec + 'https://vk.com/wall' + str(attachment['wall']['from_id']) + '_' + str(attachment['wall']['id'] + '\n' + commenturl), chatid=comment[groupid])
                else:
                    tgMsg(msg=boldnamec + '[' + attachment['type'] + ']\n' + commenturl, chatid=comment[groupid])

        # chat message
        if body['type'] == 'message_new' and vkchatid in vk2tgid:
            vkmsgid = post['conversation_message_id']
            timestamp = int(time())

            # replies
            reply_to = findReplyID(post, vkchatid, vk2tgid)

            # forwards
            vkProcessForwards(post, boldnamec, vk2tgid, vkchatid, text)

            if text != '':
                msg = boldnamec + text
                tgresult = tgMsg(msg=msg, chatid=vk2tgid[vkchatid], reply_to=reply_to)
                tgmsgid = tgresult['result']['message_id']
                checksum = adler32(text.encode('utf-8'))
                dbmsg = Message(vkmsgid=vkmsgid, tgmsgid=tgmsgid, tgchatid=vk2tgid[vkchatid], vkchatid=vkchatid, timestamp=timestamp, checksum=checksum)
                dbmsg.put()

            if geo:
                lat = geo['coordinates']['latitude']
                lon = geo['coordinates']['longitude']
                tgresult = tgLocation(lat=lat, lon=lon, chatid=vk2tgid[vkchatid], reply_to=reply_to)
                tgmsgid = tgresult['result']['message_id']
                checksum = adler32(text.encode('utf-8'))
                dbmsg = Message(vkmsgid=vkmsgid, tgmsgid=tgmsgid, tgchatid=vk2tgid[vkchatid], vkchatid=vkchatid, timestamp=timestamp, checksum=checksum)
                dbmsg.put()
                tgMsg(msg=u'Местоположение от ' + boldname, chatid=vk2tgid[vkchatid])

            for attachment in post['attachments']:
                if attachment['type'] == 'photo':
                    tgresult = tgPhoto(url=getVkPhotoUrl(attachment), caption=u'Фото от ' + boldname, chatid=vk2tgid[vkchatid])
                elif attachment['type'] == 'sticker':
                    tgresult = tgPhoto(url=getVkStickerUrl(attachment), caption=u'Стикер от ' + boldname, chatid=vk2tgid[vkchatid])
                elif attachment['type'] == 'link':
                    if text == '':
                        tgresult = tgMsg(msg=boldnamec + attachment['link']['url'], chatid=vk2tgid[vkchatid])
                elif attachment['type'] == 'wall':
                    tgresult = tgMsg(msg=boldnamec + 'https://vk.com/wall' + str(attachment['wall']['from_id']) + '_' + str(attachment['wall']['id']), chatid=vk2tgid[vkchatid])
                else:
                    tgresult = tgMsg(msg=boldnamec + '[' + attachment['type'] + ']', chatid=vk2tgid[vkchatid])
                tgmsgid = tgresult['result']['message_id']
                dbmsg = Message(vkmsgid=vkmsgid, tgmsgid=tgmsgid, tgchatid=vk2tgid[vkchatid], vkchatid=vkchatid, timestamp=timestamp)
                dbmsg.put()

        self.response.write('ok')


class tgHandler(webapp2.RequestHandler):
    def post(self):
        body = json.loads(self.request.body)
        logging.info(json.dumps(body, indent=4).decode('unicode-escape'))

        if 'message' in body:
            message = body['message']
            tgmsgid = message['message_id']
            tgchatid = message['chat']['id']

            if tgchatid in tg2vkid:
                vk_session = vk_api.VkApi(token=VKGROUPTOKEN, api_version=VKAPIVER)
                upload = vk_api.VkUpload(vk_session)
                vk = vk_session.get_api()

                fwfrom = message.get('forward_from')
                text = message.get('text', '')
                photo = message.get('photo')
                document = message.get('document')
                video = message.get('video')
                audio = message.get('audio')
                sticker = message.get('sticker')
                contact = message.get('contact')
                location = message.get('location')
                caption = message.get('caption', '')
                name = getTgName(message['from'])

                attachment = ''
                lat = ''
                lon = ''
                replytext = getReplyText(message)

                if photo:
                    for photosize in photo:
                        photo_id = photosize['file_id']
                    dfile = urlopen(tgGetFile(photo_id))
                    vkphoto = upload.photo_messages(dfile)
                    if vkphoto[0]:
                        attachment = 'photo' + str(vkphoto[0]['owner_id']) + '_' + str(vkphoto[0]['id'])
                    text = caption

                if document:
                    text = '[file] ' + caption

                if video:
                    text = '[video] ' + caption

                if audio:
                    text = '[audio] ' + caption

                if sticker:
                    text = sticker.get('emoji', '')
                    if sticker['is_animated']:
                        stickerfileid = sticker['thumb']['file_id']
                    else:
                        stickerfileid = sticker['file_id']
                    dfile = urlopen(tgGetFile(stickerfileid))
                    vkphoto = upload.photo_messages(dfile)
                    if vkphoto[0]:
                        attachment = 'photo' + str(vkphoto[0]['owner_id']) + '_' + str(vkphoto[0]['id'])

                if contact:
                    text = '[contact] ' + contact['first_name'] + ' ' + contact['phone_number']

                if location:
                    lat = location['latitude']
                    lon = location['longitude']

                if fwfrom:
                    fwname = getTgName(fwfrom)
                    text = '[forward] ' + fwname + ": " + text

                if text or attachment or lat:
                    msg = replytext + name + ": " + text
                    msg = re.sub(r'\s+$', '', msg, 0)
                    vk.messages.send(chat_id=tg2vkid[tgchatid], message=msg, attachment=attachment, lat=lat, long=lon)
                    timestamp = int(time())
                    vkchatid = int(tg2vkid[tgchatid]) + 2000000000
                    checksum = adler32(msg.encode('utf-8'))
                    dbmsg = Message(tgmsgid=tgmsgid, tgchatid=tgchatid, vkchatid=vkchatid, timestamp=timestamp, checksum=checksum)
                    dbmsg.put()


app = webapp2.WSGIApplication([
    ('/', vkHandler),
    ('/tghook', tgHandler)
])
