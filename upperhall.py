"""

upperhall.py - Extracts Upper Hall menus and exports them to an iCal file.
Ver 0.4.
Niall McConville 2016

Usage: python upperhall.py

To execute on SRCF, install modules using "pip install --user <module>"

"""

# Calendar Module
from icalendar import Calendar, Event
# BeautifulSoup processes HTML
from bs4 import BeautifulSoup
# Regular Expressions
import re
# Dates
from datetime import datetime, timedelta, time
# Raven/Shibboleth Handling - Not perfect but it seems to work
import urllib
import urllib2
import cookielib
import getpass

# Address is primarily so Google Now can figure out how long it would take you to get to Hall.
# Adjust times if they vary.
version_no = 0.4
filename = "upper_hall.html"
christs_addr = "Christ's College Cambridge, St Andrew's St, Cambridge CB2 3BU, United Kingdom"
times = {'breakfast-start': time(8,15), 
    'breakfast-end': time(9,15), 
    'lunch-start': time(12,00), 
    'lunch-end': time(13,25), 
    'dinner-start': time(17,50), 
    'dinner-end': time(19,20), 
    'sat-brunch-start': time(11,30), 
    'sat-brunch-end': time(13,25),
    'sun-brunch-start': time(10,45), 
    'sun-brunch-end': time(12,45),
    'weekend-dinner-end': time(19,10)
}

def concatenate_options(options):
    """ Concatenates a list of BeautifulSoup data, encodes to a string, and concatenates with a linespace. """
    output = ""
    for option in options:
        try:
            opt_text = option.string.encode('utf-8')
            # Some blank unicode characters make it through, so I cull them here.
            if len(opt_text) > 5:
                output += "* "+opt_text+"\n"
            else:
                pass
            # Some of the table cells are empty so truncate.
        except AttributeError:
            pass
    return output

def table_to_columns(table_rows, columns=7):
    """
    HTML does things by way of table rows, this allows for indexing by column - which is again, how the menus are structured.
    The first column of the menu is truncated as it merely provides labels for lunch and dinner.
    Output is a list of lists, where [index]: Lunch [1], Lunch Dessert [2], Dinner [4], Dinner Dessert [5]
    """
    output = [[] for x in xrange(columns)]
    for rows in table_rows:
        j = 0
        while j < columns:
            try:
                output[j].append(rows.find_all('td')[j+1].contents)
            # Sometimes an error is thrown if a cell is empty.
            except IndexError:
                output[j].append('')
            j = j + 1
    return output

def create_event(summary, start_datetime, end_datetime, location='', description=''):
    """ Returns an event object using icalendar """
    output = Event()
    output.add('summary', summary)
    output.add('dtstart', start_datetime)
    output.add('dtend', end_datetime)
    output.add('location', location)
    output.add('description', description)
    return output

def login():
    username = raw_input('Enter your crsid: ')
    password = getpass.getpass('Enter your password: ')
    return [username, password]

# iCal initialization + headers

cal = Calendar()
cal.add('prodid', '-//Upper Hall Times//')
cal.add('version', version_no)
cal.add('x-wr-calname', "Upper Hall")
cal.add('x-wr-timezone', 'Europe/London')

# Get Menus HTML (No error handling, so if something goes wrong it looks horrendous).

print "Christ's College Upper Hall iCalendar Generator. Version "+ str(version_no) + ".\nNiall McConville 2016.\n"

# URLs that we jump between in order to log into the College Intranet
login_url = 'https://intranet.christs.cam.ac.uk/Shibboleth.sso/Login?target=https%3A%2F%2Fintranet.christs.cam.ac.uk%2F%3Fdestination%3D%2F'
menu_url = 'https://intranet.christs.cam.ac.uk/upper-hall-menus'
shib_url = 'https://intranet.christs.cam.ac.uk/Shibboleth.sso/SAML2/POST'
auth_url = 'https://raven.cam.ac.uk/auth/authenticate2.html'

user_data = login()
# Post Data
values = {'userid': user_data[0], 'pwd': user_data[1], 'submit': 'Submit'}
data = urllib.urlencode(values)

print "\nAttempting to connect to College Website..."
cookies = cookielib.CookieJar()

opener = urllib2.build_opener(
    urllib2.HTTPRedirectHandler(),
    urllib2.HTTPHandler(debuglevel=0),
    urllib2.HTTPSHandler(debuglevel=0),
    urllib2.HTTPCookieProcessor(cookies))

# Login to Shibboleth (From examination of POST data)
response = opener.open(auth_url, data)
data = urllib.urlencode(values)

response2 = opener.open(login_url, data)
websoup = BeautifulSoup(response2.read(), 'html.parser')

# After intially passing login data to Shib, we then get redirected to another page before we get the final cookie.
cookie_val = websoup.find('input', {'name': 'RelayState'})['value']
SAMLResp = websoup.find('input', {'name': 'SAMLResponse'})['value']
shib_values = {'Host': 'intranet.christs.cam.ac.uk', 'Referer': 'https://shib.raven.cam.ac.uk/idp/profile/SAML2/Redirect/SSO', 'RelayState': str(cookie_val), 'SAMLResponse': str(SAMLResp), 'submit': 'Continue'}

data = urllib.urlencode(shib_values)
response3 = opener.open(shib_url, data)

# Finally, obtain the menu page.
response4 = opener.open(menu_url, data)
soup = BeautifulSoup(response4.read(), 'html.parser')

print "\nConnected!"

# Extract all Tables
menu_tables = soup.find_all('table')

# Extract date of Starting Week.
# First table contains the weeks + their start dates. Processing this means we do not have to extract the date from every table.
# Regex String shamelessly lifted from http://stackoverflow.com/posts/4896656/revisions (And will not work for leap years -> fine because term doesn't start at the end of February...)
string_to_search = menu_tables[0].find_all('a')[0].string.encode('utf-8')
regular_expression = '(0?[1-9]|[12][0-9]|3[01])[- /.](0?[1-9]|1[012])[- /.]\d\d'
m = re.search(regular_expression, string_to_search)
try:
    start_date = datetime.strptime(m.group(0), '%d/%m/%y')
except AttributeError:
    pass

# i = table id. There are 10 tables on the menu page, reject the first one as it does not contain menus.
i = 1
while i < 10:
    table = menu_tables[i]
    # Extract column data, ignoring the first column
    column_data = table_to_columns(table.find_all('tr'))
       
    # k = Day of the week (Monday=0, Tuesday=1...)
    k = 0
    while k < 7:
        date = start_date + timedelta(days=7*(i-1)+k)
 
        # Monday to Friday is Breakfast/Lunch
        if k < 5:

            breakfast_start_dtime = datetime.combine(date, times['breakfast-start'])
            breakfast_end_dtime = datetime.combine(date, times['breakfast-end'])

            cal.add_component(create_event('Breakfast', \
                breakfast_start_dtime, \
                breakfast_end_dtime, \
                christs_addr))

            lunch_start_dtime = datetime.combine(date, times['lunch-start'])
            lunch_end_dtime = datetime.combine(date, times['lunch-end'])

            description = "Menu:\n"
            description += concatenate_options(column_data[k][1])

            description += "\nDessert:\n"
            description += concatenate_options(column_data[k][2])

            cal.add_component(create_event('Lunch', \
                lunch_start_dtime, \
                lunch_end_dtime, \
                christs_addr, \
                description))

        elif k == 5:
            brunch_start_dtime = datetime.combine(date, times['sat-brunch-start'])
            brunch_end_dtime = datetime.combine(date, times['sat-brunch-end'])
            cal.add_component(create_event('Brunch', \
                brunch_start_dtime, \
                brunch_end_dtime, \
                christs_addr, \
                description))

        else:
            brunch_start_dtime = datetime.combine(date, times['sun-brunch-start'])
            brunch_end_dtime = datetime.combine(date, times['sun-brunch-end'])
            cal.add_component(create_event('Brunch', \
                brunch_start_dtime, \
                brunch_end_dtime, \
                christs_addr, \
                description))

        # Dinner
        # Adjust Dinner times dependent on whether or not it's a weekend.
        dinner_end = (times['weekend-dinner-end'], times['dinner-end'])[k < 5]

        dinner_start_dtime = datetime.combine(date, times['dinner-start'])
        dinner_end_dtime = datetime.combine(date, dinner_end)

        description = "Menu:\n"
        description += concatenate_options(column_data[k][4])

        description += "\nDessert:\n"
        description += concatenate_options(column_data[k][5])

        cal.add_component(create_event('Dinner', \
                dinner_start_dtime, \
                dinner_end_dtime, \
                christs_addr, \
                description))

        k = k + 1
    i = i + 1

# Finally, export into the calendar file.
with open('upper_hall_times.ics', 'wb') as my_file:
    my_file.writelines(cal.to_ical())

