"""Rank only cached, visible GIO application metadata; never inspect the filesystem."""
import re
import unicodedata


def normalize(text):
    text = unicodedata.normalize('NFKD', text or '').casefold()
    return ' '.join(''.join(c for c in text if not unicodedata.combining(c)).split())


def words(text):
    return tuple(re.findall(r'[^\W_]+', text, re.UNICODE))


def is_visible(app):
    return (app.should_show() and not getattr(app, 'get_is_hidden', lambda: False)()
            and app.get_id() != 'lxqt-comfort.desktop')


class AppSearchIndex:
    def __init__(self, apps):
        self.entries = []
        for app in apps:
            if not is_visible(app):
                continue
            name = normalize(app.get_display_name())
            executable = normalize(app.get_executable())
            command = executable.rsplit('/', 1)[-1]
            keywords = normalize(' '.join(app.get_keywords() or []))
            description = normalize(app.get_description())
            fields = tuple((value, words(value)) for value in (name, executable, keywords, description))
            self.entries.append((app, name, command, fields, app.get_id() or ''))

    def search(self, query):
        query = normalize(query)
        if not query:
            return []  # Empty search belongs to the existing pins/category view.
        terms = tuple(dict.fromkeys(query.split()))
        ranked = []
        for app, name, command, fields, desktop_id in self.entries:
            costs = []
            for term in terms:
                matches = []
                for index, (value, tokens) in enumerate(fields):
                    if term in tokens: matches.append(index * 3)
                    elif any(token.startswith(term) for token in tokens): matches.append(index * 3 + 1)
                    elif term in value: matches.append(index * 3 + 2)
                if not matches:
                    break
                costs.append(min(matches))
            else:
                tier = (0 if query == name else 1 if query == command else
                        2 if name.startswith(query) else
                        3 if all(any(token.startswith(term) for token in fields[0][1]) for term in terms) else 4)
                ranked.append(((tier, sum(costs), name, desktop_id), app))
        return [app for _, app in sorted(ranked, key=lambda entry: entry[0])]
