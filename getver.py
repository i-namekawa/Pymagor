import subprocess

def getstdout(cmdstrings):
    P = subprocess.Popen( cmdstrings, stdout=subprocess.PIPE )
    return P.stdout.read().splitlines()[0]

def getver():
    '''git rev-list HEAD --count'''
    return getstdout(('git', 'rev-list', 'HEAD', '--count'))

def gethex():
    '''git rev-parse HEAD'''
    return getstdout(('git', 'rev-parse', 'HEAD'))

def lastcomment():
    'git log --format=%B -n 1'
    return getstdout(('git', 'log', '--format=%B', '-n', '1'))
 
def create_infofile():
    with open('resources/version.info', 'w') as f:
        f.write(str(int(getver())+1)) # rev before commit is 1 less.
        f.write('\n')
        f.write(gethex())
        f.write('\n')

if __name__ == '__main__':
    
    print getver()
    print gethex()
    print lastcomment()
    create_infofile()
