import io
import json
import io
import json
import os
import praw
import re
import time
import urllib2

base_path = os.getcwd()
settings = json.loads(open(base_path + "/settings.json", 'r').read())

def getProfileLink(link):
	try:
		return re.findall('((http:\/\/)?(www\.)?steamcommunity.com\/(id|profiles)\/[a-zA-Z0-9_-]+(\/)?)', link)[0][0]
	except Exception as detail:
		return None

def getTradeOfferLink(link):
	try:
		return re.findall('((https?:\/\/)?(www\.)?steamcommunity.com\/tradeoffer\/new\/\?partner=\d+&token=.+(\/)?)', link)[0][0]
	except Exception as detail:
		return None

def isValidProfileLink(link):
	matches = re.match('(^|\A)(http:\/\/)?(www\.)?steamcommunity.com\/(id|profiles)\/[a-zA-Z0-9_-]+(\/)?($|\z)', link)
	return len(matches.groups()) > 0 if matches != None else False

def isValidSteamId64(steamId):
	matches = re.match('(^|\A)[0-9]{17}($|\z)', steamId)
	return len(matches.groups()) > 0 if matches != None else False

def isValidVanityId(vanityId):
	matches = re.match('(^|\A)[a-zA-Z0-9_-]+?($|\z)', vanityId)
	return len(matches.groups()) > 0 if matches != None else False

def GetSteamId64FromVanity(vanityId):
	print("\tConverting vanity ID \"" + vanityId + "\" to Steam ID 64...")
	response = json.loads(urllib2.urlopen("http://api.steampowered.com/ISteamUser/ResolveVanityURL/v0001/?key=" + settings['steam_api_key'] + "&vanityurl=" + vanityId).read())['response']['steamid']
	if isValidSteamId64(response):
		print("\t    -> Converted to " + response)
		return response
	else:
		print("\t    -> Could not be converted.")
		return None

print("Logging in...")

# Log into the moderator account.
user_agent = ("RedditSteamUrlGrabber 1.0 by /u/Jpon9")
r = praw.Reddit(user_agent=user_agent)
r.login(settings['bot']['username'], settings['bot']['password'])

print("Logged in!")
print("Getting thread...")

threadId = settings['thread_id']

# Get the thread comments in a flat list.
thread = praw.helpers.flatten_tree(r.get_submission(submission_id=threadId).comments)

print("Thread retrieved!")
print ("Grabbing entries...")

entries = []
authors = []
steamIds = []

# Grab all the Steam profile links from the thread
for comment in thread:
	profileLink = getProfileLink(comment.body)
	if profileLink != None and isValidProfileLink(profileLink) and str(comment.author) not in authors:
		entry = {}
		entry['author'] = str(comment.author)
		entry['profile'] = profileLink
		# Get the Steam ID or Vanity ID from the profile URL
		exploded = profileLink.split('/')
		steamId = exploded[len(exploded) - 1]
		# Handle if there's a slash at the end of the URL, probably a poor way to do this
		if not isValidSteamId64(steamId) and not isValidVanityId(steamId):
			steamId = exploded[len(exploded) - 2]
		# Make sure the ID we're storing is a Steam Community ID, otherwise don't store it at all
		if isValidSteamId64(steamId):
			entry['steamid'] = steamId
		elif isValidVanityId(steamId):
			entry['steamid'] = GetSteamId64FromVanity(steamId)
			time.sleep(2) # Give the Steam API some time to rest
		if entry['steamid'] == None or entry['steamid'] in steamIds:
			continue
		# Add the entry and the author/IDs so we don't get duplicates
		authors.append(str(comment.author))
		steamIds.append(entry['steamid'])
		entries.append(entry)
		print("\tUser \"" + entry['author'] + "\" added with Steam ID \"" + entry['steamid'] + "\"")
	else:
		print("\tComment ID \"" + comment.id + "\" did not contain a valid profile link or was a duplicate.")

print("All entries grabbed.")

# Write the entries to a JSON file for storage/debugging
with io.open(base_path + "/entries.json", 'w', encoding='utf-8') as f:
	f.write(unicode(json.dumps(entries, ensure_ascii=False, indent=4, separators=(',', ': '))))