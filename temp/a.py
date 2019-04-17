from bs4 import BeautifulSoup
import re

test = '<p> &nbsp; &nbsp; &nbsp; This &nbsp; is &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; ' \
       'Test String \n &nbsp; &nbsp; &nbsp; &nbsp; to test &nbsp; &nbsp; &nbsp; duplicate spaces &nbsp; </p><p>&nbsp;hkkjjlkjl</p> '
soup = BeautifulSoup(test, 'html.parser')

# for str in soup.find_all('p'):
#     print(str)
#     print(str.p.prettify())
#
# print(soup.prettify())
for string in soup.find_all():
    print(string.text)
    print('---------')
    if len(string.text) == 0:
        print('inside')
        print(string.extract())


# for string in soup.strings:
#     print(repr(string))
#
#
# for space in soup.find_all():
#     print(space)
    # if len(space.text) != 0:
    #     print(space)

    # print('string', string.strip())
    # print('extract', re.sub('\s+', ' ', string).strip())

