import tempfile
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from menu.app_search import AppSearchIndex


def app(name, command='', keywords=(), description='', visible=True, desktop_id=None):
    a=Mock();a.get_is_hidden.return_value=False;a.should_show.return_value=visible;a.get_id.return_value=desktop_id or name+'.desktop'
    a.get_display_name.return_value=name;a.get_executable.return_value=command
    a.get_keywords.return_value=keywords;a.get_description.return_value=description
    return a


class AppSearchTests(unittest.TestCase):
    def test_rank_exact_name_command_prefix_tokens_and_description(self):
        exact=app('Code');prefix=app('Code Editor');tokens=app('Visual Code');exe=app('Editor','/usr/bin/code');desc=app('Aardvark',description='Write code')
        self.assertEqual(AppSearchIndex([desc,tokens,prefix,exe,exact]).search('code'),[exact,exe,prefix,tokens,desc])

    def test_cross_field_and_reordered_tokens(self):
        a=app('Visual Studio Code','/usr/bin/code',['Programming','Editor']);b=app('Audio Studio',keywords=['Recording'])
        index=AppSearchIndex([a,b])
        self.assertEqual(index.search('editor visual'),[a]);self.assertEqual(index.search('code studio'),[a])
        self.assertEqual(index.search('studio absent'),[])
        self.assertEqual(index.search('cord'),[b])

    def test_unicode_case_accents_whitespace_and_punctuation(self):
        a=app('Éditeur Straße');b=app('日本語 Editor');c=app('C++ Builder')
        index=AppSearchIndex([a,b,c])
        for query in ('EDITEUR STRASSE','e\u0301diteur','  STRASSE  '):self.assertEqual(index.search(query),[a])
        self.assertEqual(index.search('日本'),[b]);self.assertEqual(index.search('c++'),[c])
        self.assertEqual(index.search(' \t\n '),[])

    def test_visibility_exclusions_and_deterministic_ties(self):
        hidden=app('Secret',visible=False);selfentry=app('Secret',desktop_id='lxqt-comfort.desktop')
        a=app('Visible',desktop_id='a.desktop');b=app('Visible',desktop_id='b.desktop')
        self.assertEqual(AppSearchIndex([hidden,selfentry,b,a]).search('visible'),[a,b])
        self.assertEqual(AppSearchIndex([hidden,selfentry]).search('secret'),[])

    def test_search_never_requeries_metadata(self):
        a=app('Editor','/usr/bin/edit',['Text']);index=AppSearchIndex([a])
        for member in ('get_display_name','get_executable','get_keywords','get_description','should_show','get_id'):
            getattr(a,member).side_effect=AssertionError('metadata read during query')
        for text in ('ed','text','/usr/bin/edit','none'):index.search(text)

    def test_actual_desktop_visibility_rules(self):
        from gi.repository import Gio
        with tempfile.TemporaryDirectory() as tmp:
            entries=[]
            for name,extra in [('Visible',''),('NoDisplay','NoDisplay=true\n'),('Hidden','Hidden=true\n'),('WrongDesktop','OnlyShowIn=NeverDoroShell;\n')]:
                path=Path(tmp)/(name+'.desktop');path.write_text('[Desktop Entry]\nType=Application\nName=Fixture '+name+'\nExec=/usr/bin/true\n'+extra)
                a=Gio.DesktopAppInfo.new_from_filename(str(path))
                if a:entries.append(a)
            self.assertEqual([a.get_display_name() for a in AppSearchIndex(entries).search('fixture')],['Fixture Visible'])

    def test_installed_module_repeat_and_rollback(self):
        import contextlib,io,os,subprocess
        import install
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            home=Path(tmp);target=home/'.local/share/lxqt-comfort/app_search.py';target.parent.mkdir(parents=True)
            target.write_bytes(b'# original local module\n');target.chmod(0o640)
            for _ in range(2):install.install(home,apply=True)
            expected=(Path(__file__).resolve().parents[1]/'menu/app_search.py').read_bytes()
            self.assertEqual(target.read_bytes(),expected)
            self.assertEqual((home/'.local/share/doroshell/toolkit/menu/app_search.py').read_bytes(),expected)
            env=dict(os.environ);env.pop('PYTHONPATH',None)
            subprocess.run([sys.executable,'-c','import sys;sys.path.insert(0,sys.argv[1]);import start_menu;assert start_menu.AppSearchIndex([]).search("a")==[]',str(target.parent)],cwd=home,env=env,check=True,capture_output=True)
            install.rollback(home)
            self.assertEqual(target.read_bytes(),b'# original local module\n')
            self.assertEqual(target.stat().st_mode&0o777,0o640)
