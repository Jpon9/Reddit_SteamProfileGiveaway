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
	print("\t\tConverting vanity ID \"" + vanityId + "\" to Steam ID 64...")
	tries = 0
	while True:
		errorOccurred = False
		try:
			tries += 1
			response = json.loads(urllib2.urlopen("http://api.steampowered.com/ISteamUser/ResolveVanityURL/v0001/?key=" + settings['steam_api_key'] + "&vanityurl=" + vanityId, None, 45).read())['response']['steamid']
		except urllib2.URLError as detail:
			print("\t\t    -> Exception caught resolving vanity ID, retrying in five seconds...")
			errorOccurred = True
		if errorOccurred == False:
			break
		if tries >= 3:
			print("\t\t    -> Three strikes, skipping this ID.")
			response = vanityId
			break
		time.sleep(5) # Give the Steam API some time before retrying

	time.sleep(2) # Give the Steam API time to rest
	if isValidSteamId64(response):
		print("\t\t    -> Converted to " + response)
		return response
	else:
		print("\t\t    -> Could not be converted.")
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
invalid = []

# Grab all the Steam profile links from the thread
for comment in thread:
	profileLink = getProfileLink(comment.body)
	if profileLink != None and isValidProfileLink(profileLink) and str(comment.author) not in authors:
		entry = {}
		entry['author'] = str(comment.author)
		entry['profile'] = profileLink
		entry['body'] = comment.body
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
		if entry['steamid'] == None or entry['steamid'] in steamIds:
			continue
		# Add the entry and the author/IDs so we don't get duplicates
		authors.append(entry['author'])
		steamIds.append(entry['steamid'])
		entries.append(entry)
		print("\tUser \"" + entry['author'] + "\" added with Steam ID \"" + entry['steamid'] + "\"")
	else:
		invalid.append({"author":str(comment.author),"id":comment.id,"body":comment.body})

print("All entries grabbed.")
print("Checking account ages...")

batches = [[]]
batchSize = 50

for steamId in steamIds:
	if len(batches[len(batches) - 1]) >= batchSize:
		batches.append([])
	batches[len(batches) - 1].append(steamId)

profileSummaries = []

batchesFetched = 0
for batch in batches:
	tries = 0
	batchesFetched += 1
	print("\tFetching Batch #" + str(batchesFetched))
	while True:
		errorOccurred = False
		try:
			tries += 1
			summaries = json.loads(urllib2.urlopen("http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key=" + settings['steam_api_key'] + "&steamids=" + ",".join(batch), None, 60).read())['response']['players']
		except urllib2.URLError as detail:
			print("\t\t    -> Exception caught grabbing profile summaries, retrying in five seconds...")
			errorOccurred = True
		if errorOccurred == False:
			break
		if tries >= 3:
			print("\t\t    -> Three strikes, skipping this batch.")
			break
		time.sleep(5) # Give the Steam API some time before retrying
	print("\tBatch #" + str(batchesFetched) + " has been fetched.")
	time.sleep(2) # Give the Steam API time to rest
	profileSummaries += summaries

print("All batches have been fetched.")
print("There are " + str(len(profileSummaries)) + " entries.")
print("Purging accounts made after December 5th...")

acceptedEntries = []

for summary in profileSummaries:
	if summary['timecreated'] <= 1417737600:
		acceptedEntries.append(summary['profileurl'])

print("There are now " + str(len(acceptedEntries)) + " entries.")
print("Dumping valid Steam profiles into valid-entries.json.")

# Write the valid profile URLs to a JSON file for storage/debugging
with io.open(base_path + "/valid-entries.json", 'w', encoding='utf-8') as f:
	f.write(unicode(json.dumps(acceptedEntries, ensure_ascii=False, indent=4, separators=(',', ': '))))

# Write the profile summaries to a JSON file for storage/debugging
with io.open(base_path + "/profile-summaries.json", 'w', encoding='utf-8') as f:
	f.write(unicode(json.dumps(profileSummaries, ensure_ascii=False, indent=4, separators=(',', ': '))))

# Write the batches to a JSON file for storage/debugging
with io.open(base_path + "/batches.json", 'w', encoding='utf-8') as f:
	f.write(unicode(json.dumps(batches, ensure_ascii=False, indent=4, separators=(',', ': '))))

# Write the entries to a JSON file for storage/debugging
with io.open(base_path + "/entries.json", 'w', encoding='utf-8') as f:
	f.write(unicode(json.dumps(entries, ensure_ascii=False, indent=4, separators=(',', ': '))))

# Write the invalid entries to a JSON file for storage/debugging
with io.open(base_path + "/invalid-comments.json", 'w', encoding='utf-8') as f:
	f.write(unicode(json.dumps(invalid, ensure_ascii=False, indent=4, separators=(',', ': '))))