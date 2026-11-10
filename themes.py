"""Optional Doro palettes and narrowly owned desktop theme settings."""
import base64
import json
from pathlib import Path

PALETTES = {
    'windows': dict(name='Windows Doro', base='#fff5fb', window='#f4dce9', ink='#351329', muted='#715064', accent='#934369', selection='#edafd2', side='#773353', edge='#b9799e'),
    'polar': dict(name='Polar Doro', base='#f4fbff', window='#dceef9', ink='#14324a', muted='#46647a', accent='#28618d', selection='#a8d5f4', side='#244f73', edge='#7aa7c5'),
    'heretic': dict(name='Heretic Doro', base='#222124', window='#302c30', ink='#f8eeee', muted='#c3aeb6', accent='#d97682', selection='#70323d', side='#211c20', edge='#a65c68'),
    'spring': dict(name='Spring Doro', base='#fffdf0', window='#e6edd0', ink='#243b23', muted='#53694d', accent='#466e37', selection='#c0d89c', side='#3c5a30', edge='#849b64'),
}


def glass(color, alpha):
    return '#' + alpha + color[1:]


def menu_style(p, composited=False):
    frame_top = glass(p['window'], 'ed') if composited else p['window']
    frame_accent = glass(p['selection'], 'e0') if composited else p['selection']
    side = glass(p['side'], 'ed') if composited else p['side']
    return f"""
        QWidget#glassFrame {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {frame_top},stop:0.48 {frame_accent},stop:1 {frame_top}); border: 1px solid {p['edge']}; }}
        QWidget#applicationsPanel, QMenu, QMessageBox {{ background: {p['base']}; color: {p['ink']}; border: 1px solid {p['edge']}; }}
        QWidget#applicationsPanel QLabel, QWidget#applicationsPanel QPushButton, QMessageBox QLabel {{ color: {p['ink']}; }}
        QWidget#placesPanel {{ background: {side}; }}
        QWidget#placesPanel QLabel, QWidget#placesPanel QPushButton {{ color: #fff5fb; }}
        QLabel#personalStartImage {{ background: {p['window']}; border: 1px solid {p['edge']}; }}
        QListWidget, QLineEdit, QComboBox, QComboBox QAbstractItemView {{ background: {p['base']}; color: {p['ink']}; border-color: {p['edge']}; }}
        QLineEdit {{ placeholder-text-color: {p['muted']}; }}
        QListWidget::item:selected, QListWidget::item:hover, QComboBox QAbstractItemView::item:selected,
        QPushButton:hover, QPushButton:focus, QMenu::item:selected {{ background: {p['selection']}; color: {p['ink']}; border-color: {p['edge']}; }}
        QWidget#placesPanel QPushButton:hover, QWidget#placesPanel QPushButton:focus,
        QPushButton[sessionPrimary="true"], QPushButton#powerMenuArrow {{ background: {p['side']}; color: #fff5fb; border: 1px solid {p['edge']}; }}
        QMessageBox QPushButton {{ background: {p['base']}; color: {p['ink']}; border-color: {p['edge']}; }}
        QPushButton:disabled, QMenu::item:disabled {{ color: {p['muted']}; }}
        QWidget#placesPanel QPushButton[sessionPrimary="true"], QWidget#placesPanel QPushButton#powerMenuArrow {{ color: #fff5fb; }}
        QPushButton#programsButton {{ border-top-color: {p['edge']}; }}
        QWidget#placesPanel QPushButton:disabled {{ color: #c8bdc4; }}
        QToolButton#folderBrowse {{ color: #fff5fb; background: transparent; }}
        QToolButton#folderBrowse:hover, QToolButton#folderBrowse:focus {{ background: {p['side']}; border-color: {p['edge']}; }}
    """


def panel_style(p, composited=False):
    surface = glass(p['window'], 'f0') if composited else p['window']
    shine = glass(p['selection'], 'f0') if composited else p['selection']
    return f"""
        LXQtPanel #BackgroundWidget {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {surface},stop:0.48 {shine},stop:0.5 {surface},stop:1 {surface}); border-top: 1px solid {p['edge']}; }}
        QLabel#WorldClockContent, LXQtTaskButton, QuickLaunchButton, QToolButton#doroshellTrayArrow {{ color: {p['ink']}; }}
        LXQtTaskButton:hover, QuickLaunchButton:hover, QToolButton#doroshellTrayArrow:hover {{ background: {p['selection']}; border-color: {p['edge']}; }}
        LXQtTaskButton[doroshellRunning="true"] {{ border-bottom: 2px solid {p['accent']}; }}
        QFrame#doroshellTrayPopup {{ background: {p['side']}; color: #fff5fb; border-color: {p['edge']}; }}
        QFrame#doroshellTrayPopup QToolButton {{ background: transparent; color: #fff5fb; border: 1px solid transparent; border-radius: 4px; }}
        QFrame#doroshellTrayPopup QToolButton:hover, QFrame#doroshellTrayPopup QToolButton:focus {{ background: {p['side']}; border-color: #fff5fb; }}
        QToolButton[doroshellEdge="true"] {{ background: {p['window']}; border-color: {p['edge']}; }}
    """


def theme_files(p):
    """Original colors and geometry. Personal images are never bundled."""
    colors = '[General]\nName=DoroShell\nColorScheme=DoroShell\n'
    for group in ('Window', 'View', 'Button', 'Selection', 'Tooltip', 'Complementary', 'Header'):
        bg = p['selection'] if group == 'Selection' else p['base'] if group in ('View','Tooltip') else p['window']
        colors += f'\n[Colors:{group}]\n'
        for key, value in dict(BackgroundNormal=bg, BackgroundAlternate=p['window'], ForegroundNormal=p['ink'],
                               ForegroundInactive=p['muted'], ForegroundActive=p['accent'], ForegroundLink=p['accent'],
                               ForegroundVisited=p['muted'], ForegroundNegative=p['accent'], ForegroundNeutral=p['accent'],
                               ForegroundPositive=p['accent'], DecorationFocus=p['accent'], DecorationHover=p['edge']).items():
            colors += key+'='+','.join(str(int(value[i:i+2],16)) for i in (1,3,5))+'\n'
    colors += '\n[ColorEffects:Disabled]\nEnable=false\n'
    ob = f"""border.width: 1
padding.width: 5
padding.height: 4
window.handle.width: 3
window.active.border.color: {p['accent']}
window.active.client.color: {p['window']}
window.inactive.client.color: {p['window']}
window.inactive.border.color: {p['edge']}
window.active.title.bg: gradient vertical
window.active.title.bg.color: {p['window']}
window.active.title.bg.colorTo: {p['selection']}
window.inactive.title.bg: flat solid
window.inactive.title.bg.color: {p['window']}
window.*.label.bg: parentrelative
window.active.label.text.color: {p['ink']}
window.inactive.label.text.color: {p['muted']}
window.*.button.*.bg: parentrelative
window.active.button.*.image.color: {p['ink']}
window.inactive.button.*.image.color: {p['muted']}
window.active.button.*.hover.bg: flat solid
window.active.button.*.hover.bg.color: {p['selection']}
menu.title.bg: flat solid
menu.title.bg.color: {p['side']}
menu.title.text.color: #fff5fb
menu.items.bg: flat solid
menu.items.bg.color: {p['base']}
menu.items.text.color: {p['ink']}
menu.items.disabled.text.color: {p['muted']}
menu.items.active.bg: flat solid
menu.items.active.bg.color: {p['selection']}
menu.items.active.text.color: {p['ink']}
"""
    styles = {}
    for name in ('Normal','Keyword','Function','Variable','ControlFlow','Operator','BuiltIn','Extension','Preprocessor',
                 'Attribute','Char','SpecialChar','String','VerbatimString','SpecialString','Import','DataType','DecVal',
                 'BaseN','Float','Constant','Comment','Documentation','Annotation','CommentVar','RegionMarker',
                 'Information','Warning','Alert','Error','Others'):
        styles[name] = {'text-color': p['muted'] if name in ('Comment','Documentation') else p['ink'],
                        'selected-text-color': p['ink'], 'bold': name in ('Keyword','ControlFlow','Alert'),
                        'italic': name in ('Comment','Documentation'), 'underline': name == 'Error'}
    editor = dict(BackgroundColor=p['base'], CurrentLine=p['window'], IconBorder=p['window'],
                  LineNumbers=p['muted'], CurrentLineNumber=p['ink'], TextSelection=p['selection'],
                  BracketMatching=p['selection'], SearchHighlight=p['selection'], ReplaceHighlight=p['selection'],
                  CodeFolding=p['edge'], IndentationLine=p['edge'], Separator=p['edge'], WordWrapMarker=p['edge'],
                  TabMarker=p['edge'], SpellChecking=p['accent'], MarkBookmark=p['accent'], ModifiedLines=p['accent'],
                  SavedLines=p['edge'], MarkError=p['accent'], MarkWarning=p['accent'])
    kate = {'metadata': {'name':'DoroShell', 'revision':1, 'license':'MIT', 'copyright':['DoroShell theme contributors']},
            'text-styles':styles, 'editor-colors':editor}
    return {
        '.config/doroshell/start-theme.qss': menu_style(p),
        '.config/doroshell/start-theme-glass.qss': menu_style(p, True),
        '.config/doroshell/panel-theme.qss': panel_style(p),
        '.config/doroshell/panel-theme-glass.qss': panel_style(p, True),
        '.local/share/color-schemes/DoroShell.colors': colors,
        '.local/share/org.kde.syntax-highlighting/themes/doroshell.theme': json.dumps(kate,indent=2),
        '.local/share/themes/DoroShell/openbox-3/themerc': ob,
    }


def plans(home, name):
    if name not in PALETTES:
        raise ValueError('Choose windows, polar, heretic or spring')
    p = PALETTES[name]
    edits = [{'file':key, 'kind':'file', 'after':base64.b64encode(value.encode()).decode()}
             for key,value in theme_files(p).items()]
    def ini(file, section, key, value):
        edits.append(dict(file=file,kind='ini',section=section,key=key,after=value))
    ini('.config/doroshell/theme.conf','Theme','name',name)
    for app in ('kate','dolphin'):
        ini('.config/'+app+'rc','UiSettings','ColorScheme','DoroShell')
        ini('.config/'+app+'rc','KDE','widgetStyle','Fusion')
    ini('.config/katerc','KTextEditor Renderer','Color Theme','DoroShell')
    ini('.config/katerc','KTextEditor Renderer','Auto Color Theme Selection','false')
    palette = dict(base_color=p['base'],window_color=p['window'],text_color=p['ink'],window_text_color=p['ink'],
                   highlight_color=p['selection'],highlighted_text_color=p['ink'],link_color=p['accent'],
                   link_visited_color=p['muted'],tooltip_base_color=p['base'],tooltip_text_color=p['ink'])
    for key,value in palette.items():
        ini('.config/lxqt/lxqt.conf','Palette',key,value)
    ini('.config/lxqt/lxqt.conf','Qt','style','Fusion')
    ini('.config/lxqt/lxqt.conf','General','icon_theme','breeze-dark' if name=='heretic' else 'breeze')
    ini('.config/lxqt/lxqt.conf','General','icon_follow_color_scheme','false')
    edits.append(dict(file='.config/openbox/rc.xml',kind='obtheme',after='DoroShell'))
    return edits
