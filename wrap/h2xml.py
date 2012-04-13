"""h2xml - convert C include file(s) into an xml file by running gccxml."""
import sys, os, tempfile
import cparser
from optparse import OptionParser

if sys.platform == "win32":

    def _locate_gccxml():
        import _winreg
        for subkey in (r"Software\gccxml", r"Software\Kitware\GCC_XML"):
            for root in (_winreg.HKEY_CURRENT_USER, _winreg.HKEY_LOCAL_MACHINE):
                try:
                    hkey = _winreg.OpenKey(root, subkey, 0, _winreg.KEY_READ)
                except WindowsError, detail:
                    if detail.errno != 2:
                        raise
                else:
                    return _winreg.QueryValueEx(hkey, "loc")[0] + r"\bin"

    loc = _locate_gccxml()
    if loc:
        os.environ["PATH"] = loc

################################################################

def main():

    def add_option(option, opt, value, parser):
        parser.values.gccxml_options.extend((opt, value))

    parser = OptionParser("usage: %prog includefile ... [options]")
##    parser.add_option("-h", action="help")
    parser.add_option("-q", "--quiet",
                      dest="quiet",
                      action="store_true",
                      default=False)

    parser.add_option("-D",
                      type="string",
                      action="callback",
                      callback=add_option,
                      dest="gccxml_options",
                      help="macros to define",
                      metavar="NAME[=VALUE]",
                      default=[])
    parser.add_option("-U",
                      type="string",
                      action="callback",
                      callback=add_option,
                      help="macros to undefine",
                      metavar="NAME")

    parser.add_option("-I",
                      type="string",
                      action="callback",
                      callback=add_option,
                      dest="gccxml_options",
                      help="additional include directories",
                      metavar="DIRECTORY")

    parser.add_option("-o",
                      dest="xmlfile",
                      help="XML output filename",
                      default=None)
    options, files = parser.parse_args()

    if not files:
        print "Error: no files to process"
        print >> sys.stderr, __doc__
        return 1

    options.flags = options.gccxml_options

    options.verbose = not options.quiet

    try:
        parser = cparser.IncludeParser()
        parser.parse(files, options)
    except cparser.CompilerError, detail:
        import traceback
        traceback.print_exc()
##        print detail
        sys.exit(1)

if __name__ == "__main__":
    main()
