import platform

def get_windows_version():
    return platform.system() + ' ' + platform.release()

if __name__ == '__main__':
    print(get_windows_version())