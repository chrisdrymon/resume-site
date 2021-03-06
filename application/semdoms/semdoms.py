from flask import Blueprint
from nltk.corpus import wordnet as wn
from collections import Counter
import plotly.graph_objects as go
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.exceptions import PreventUpdate
from dash.dependencies import Input, Output, State
import os
import random
import json
import pandas as pd
import string
import requests
import re
from cltk.corpus.utils.formatter import cltk_normalize
from cltk.lemmatize.greek.backoff import BackoffGreekLemmatizer
from greek_accentuation.syllabify import *
from greek_accentuation.accentuation import *

# Blueprint Configuration
semdoms_bp = Blueprint('semdoms_bp', __name__,
                       static_folder='static',
                       template_folder='templates',
                       static_url_path='/semdoms/static')

aeinput = "άἀἁἂἃἄἅἆἇὰάᾀᾁᾂᾃᾄᾅᾆᾇᾰᾱᾲᾳᾴᾶᾷᾈᾉᾊᾋᾌᾍᾎᾏᾼἈἉΆἊἋἌἍἎἏᾸᾹᾺΆέἐἑἒἓἔἕὲέἘἙἚἛἜἝΈῈΈ"
aeoutput = "αααααααααααᾳᾳᾳᾳᾳᾳᾳᾳααᾳᾳᾳαᾳᾼᾼᾼᾼᾼᾼᾼᾼᾼΑΑΑΑΑΑΑΑΑΑΑΑΑεεεεεεεεεΕΕΕΕΕΕΕΕΕ"
hoinput = "ᾘᾙᾚᾛᾜᾝᾞᾟῌΉῊΉἨἩἪἫἬἭἮἯήἠἡἢἣἤἥἦἧὴήῆᾐᾑᾒᾓᾔᾕᾖᾗῂῃῄῇὀὁὂὃὄὅόὸόΌὈὉὊὋὌὍῸΌ"
hooutput = "ῌῌῌῌῌῌῌῌῌΗΗΗΗΗΗΗΗΗΗΗηηηηηηηηηηηηῃῃῃῃῃῃῃῃῃῃῃῃοοοοοοοοοΟΟΟΟΟΟΟΟΟ"
iuinput = "ΊῘῙῚΊἸἹἺἻἼἽἾἿΪϊίἰἱἲἳἴἵἶἷΐὶίῐῑῒΐῖῗΫΎὙὛὝὟϓϔῨῩῪΎὐὑὒὓὔὕὖὗΰϋύὺύῠῡῢΰῦῧ"
iuoutput = "ΙΙΙΙΙΙΙΙΙΙΙΙΙΙιιιιιιιιιιιιιιιιιιιΥΥΥΥΥΥΥΥΥΥΥΥυυυυυυυυυυυυυυυυυυυ"
wrinput = "ώὠὡὢὣὤὥὦὧὼῶώᾠᾡᾢᾣᾤᾥᾦᾧῲῳῴῷΏὨὩὪὫὬὭὮὯῺΏᾨᾩᾪᾫᾬᾭᾮᾯῼῤῥῬ"
wroutput = "ωωωωωωωωωωωωῳῳῳῳῳῳῳῳῳῳῳῳΩΩΩΩΩΩΩΩΩΩΩῼῼῼῼῼῼῼῼῼρρΡ"
# Strings to feed into translator tables to remove diacritics.
aelphas = str.maketrans(aeinput, aeoutput, "⸀⸁⸂⸃·,.—")
# This table also removes text critical markers and punctuation.
hoes = str.maketrans(hoinput, hooutput, string.punctuation)
# Removes other punctuation in case I forgot any.
ius = str.maketrans(iuinput, iuoutput, '0123456789')
# Also removes numbers (from verses).
wros = str.maketrans(wrinput, wroutput, string.ascii_letters)


# Also removes books names.
def deaccent(dastring):
    """Returns an unaccented version of a string."""
    return dastring.translate(aelphas).translate(hoes).translate(ius).translate(wros).lower()


# If a Greek word is given while in Greek mode and the orignal word is not in the list of Greek nouns, this will
# attempt to normalize the accentuation, try a series of accentuation patterns, and finally try to lemmatize the word.
# At each step, it will check if the resulting word is in the list of Greek nouns. Accents are easy to mess up in
# Ancient Greek, so this checks that. It should also allow for the entering of unaccented words, which is somewhat
# popular.
def greek_word_check(word):
    """If the initial word is not found in the list of available Greek nouns, then this will attempt to find a suitable
    word by accent normalization, altering accentuation patterns, and lemmatization."""
    if word.isascii():
        try:
            url = f'https://greekwordnet.chs.harvard.edu/translate/en/{word}/n/'
            trans_json = requests.get(url).json()
            word = random.choice(trans_json['results'])['lemma']
            if word in greek_nouns:
                return word
        except IndexError:
            return word
    if word in greek_nouns:
        return word
    norm_word = cltk_normalize(word)
    if norm_word in greek_nouns:
        return word
    unaccented_word = deaccent(word)
    try:
        s = syllabify(unaccented_word)
        for accentuation in possible_accentuations(s):
            next_pattern = rebreath(add_accent(s, accentuation))
            if next_pattern in greek_nouns:
                return next_pattern
            breathed_pattern = rebreath('h' + add_accent(s, accentuation))
            if breathed_pattern in greek_nouns:
                return breathed_pattern
    except TypeError:
        pass
    lemmatizer = BackoffGreekLemmatizer()
    lemmed_word = lemmatizer.lemmatize([word])[0][1]
    if lemmed_word in greek_nouns:
        return lemmed_word
    try:
        s = syllabify(word)
        for accentuation in possible_accentuations(s):
            try_word = lemmatizer.lemmatize([rebreath(add_accent(s, accentuation))])[0][1]
            if try_word in greek_nouns:
                return try_word
            try_word = lemmatizer.lemmatize([rebreath('h' + add_accent(s, accentuation))])[0][1]
            if try_word in greek_nouns:
                return try_word
    except TypeError:
        pass
    else:
        return word


def eng_synset_counting(ss_list, ss_counter, pairs):
    """A recursive function for climbing the synset hierarchy and recording the child-parent pairs."""
    next_list = []
    if len(ss_list) == 0:
        return ss_counter, pairs
    else:
        for ss in ss_list:
            for higherss in ss.hypernyms():
                if ss in pairs:
                    if higherss in pairs[ss]:
                        pass
                    else:
                        pairs[ss].append(higherss)
                else:
                    pairs[ss] = [higherss]
                ss_counter[higherss] += 1
                if higherss != wn.synset('entity.n.01'):
                    next_list.append(higherss)
        return eng_synset_counting(next_list, ss_counter, pairs)


def make_dash(word, lingua):
    """This updates the app's figure and panels when a new entry is given."""
    base_synsets = []
    basepaths = []
    multiparents = []
    synset_counter = Counter()
    child_parent_pairs = {}
    glosses = []

    if word is None:
        raise PreventUpdate

    if word == "":
        raise PreventUpdate

    # Check for language
    if lingua == 'english':

        right_box_2 = [html.H3('Definitions', style={'text-align': 'center'}), html.Br()]

        # WordNet can handle some multiword phrases, but they need underscores instead of spaces
        word = word.replace(' ', '_')
        show_word = word.replace('_', ' ')

        # Create a list of all base synsets
        for synset in wn.synsets(word, pos=wn.NOUN):
            for path in synset.hypernym_paths():
                basepaths.append(path)
            base_synsets.append(synset)

        # Order the base synsets list, grab their definitions, and format them for display in the app
        for synset in sorted(base_synsets):
            ss_split = str(synset)[8:].split('.n.')
            right_box_2.append(html.B(ss_split[0].replace('_', ' ')))
            right_box_2.append(html.Span(ss_split[1][:2].lstrip('0'), className='ss'))
            right_box_2.append(' ' + synset.definition())
            right_box_2.append(html.Br())

        synset_counter, child_parent_pairs = eng_synset_counting(base_synsets, synset_counter, child_parent_pairs)
        for child in child_parent_pairs:
            if len(child_parent_pairs[child]) > 1:
                multiparents.append(child)

        adjusted_paths = []
        max_len = 0
        for path in basepaths:
            # This number will be displayed in the app.
            if len(path) > max_len:
                max_len = len(path)
            # The tricky part here is converting the output of WordNet which sometimes assigns multiple hypernyms to a
            # single synset into the input for plotly which requires that each synset only have a single parent. So
            # renaming had to be done to synsets with multiple parents.
            multi = False
            revised_path = []
            multi_suffix = ''
            for k, item in enumerate(path):
                if multi:
                    if item in multiparents:
                        multi_suffix = multi_suffix + '-' + str(path[k - 1])
                        revised_path.append(str(item) + '-' + multi_suffix)
                    else:
                        revised_path.append(str(item) + '-' + str(multi_suffix))
                else:
                    if item in multiparents:
                        multi_suffix = str(path[k - 1])
                        revised_path.append(str(item) + '-' + multi_suffix)
                        multi = True
                    else:
                        revised_path.append(str(item))
            adjusted_paths.append(revised_path)

        ids = ["Synset('entity.n.01')"]
        labels = ['entity']
        parents = ['']
        for path in adjusted_paths:
            for j, node in enumerate(path):
                if node not in ids:
                    ids.append(node)
                    labels.append(node.split('.n')[0][8:].replace('_', ' '))
                    parents.append(path[j - 1])

        # This checks to see if WordNet recognizing the word as a noun. If not, it returns an error.
        if len(wn.synsets(word, pos=wn.NOUN)) == 0:
            graph_title = f'Error: WordNet does not recognize "{show_word.capitalize()}" as a noun.'
            figure = {'data': [{'type': 'sunburst'}]}
        else:
            graph_title = f'Semantic Domains of "{show_word.capitalize()}"'
            figure = {'data': [{'type': 'sunburst',
                                'ids': ids,
                                'labels': labels,
                                'parents': parents,
                                'hovertext': ids,
                                'hoverinfo': 'text'}],
                      'layout': {'font': {'family': 'Quicksand',
                                          'size': 24},
                                 'margin': {'l': 10,
                                            'r': 10,
                                            'b': 10,
                                            't': 10},
                                 'colorway': ['#457b9d', '#e63946']
                                 }
                      }

        right_box_1 = ['The noun "', html.B(f'{show_word}'), '" is a member of', html.H1(str(len(base_synsets))),
                       ' leaf node synsets.']
        right_box_3 = ['Unique paths from leaf nodes to root node:', html.H1(len(basepaths))]
        right_box_4 = ['Synsets along the longest path from leaf node to root node (including the leaf node and root '
                       'node):', html.H1(max_len)]
        box2c = 'sense-box'
        box3c = 'right-box'

    # If Greek is the language..
    else:
        # Find lemma id's from lemma, get synsets from lemma id's, get glosses from the synset dataframe
        # As it is, this prefers to only show glosses for synsets which are assigned a semfield. If none have a semfield
        # assigned, then it shows all glosses. This was done because some words have a huge number of glosses.
        ids = []
        labels = []
        codes = []
        parents = []
        right_box_3 = [html.H3('Definitions', style={'text-align': 'center'}), html.Br()]
        box2c = 'right-box'
        box3c = 'sense-box'
        word = greek_word_check(word)

        # WordNet can handle some multiword phrases, but they need underscores instead of spaces
        show_word = word.replace('_', ' ')

        lillemma = lemma_df[lemma_df['lemma'] == word]
        for lemma_id in lillemma['id'].to_list():
            for synset_id in list(set(sense_df[sense_df['lemma'] == lemma_id]['synset'].to_list())):
                small_ss_df = synset_df[(synset_df['id'] == synset_id) & (synset_df['semfield'].notna())]
                for gloss in small_ss_df['gloss'].to_list():
                    glosses.append(gloss)
                for semfield in small_ss_df['semfield'].to_list():
                    # If there are multiple semantic fields, this separates those up. In this case, base_synsets are
                    # id numbers,not words.
                    if isinstance(semfield, str):
                        for item in semfield.split(','):
                            base_synsets.append(int(item))
                    else:
                        if semfield:
                            base_synsets.append(semfield)

        base_synsets = list(set(base_synsets))

        # In case no glosses are assigned a semantic field:
        if len(glosses) == 0:
            for lemma_id in lemma_df[lemma_df['lemma'] == word]['id'].to_list():
                for synset_id in list(set(sense_df[sense_df['lemma'] == lemma_id]['synset'].to_list())):
                    for gloss in synset_df[(synset_df['id'] == synset_id) &
                                           (synset_df['semfield'].isnull())]['gloss'].to_list():
                        glosses.append(gloss)
            right_box_3.append(f'No definitions available for {show_word}.')
            box3c = 'right-box'
        else:
            for i, definition in enumerate(glosses):
                right_box_3.append(str(i + 1) + '. ' + re.split('[:;] "', definition)[0])
                right_box_3.append(html.Br())

        # Convert synsets to ids, labels, parents, and codes (which will be mouse hover data). The hypernym value is 0
        # when there are no higher synsets.
        for ssid in base_synsets:
            next_id = ssid
            while semfield_df[semfield_df['id'] == next_id].iloc[0]['hypers'] != 0:
                lilsf_df = semfield_df[semfield_df['id'] == next_id]
                if next_id not in ids:
                    ids.append(next_id)
                    labels.append(lilsf_df.iloc[0]['english'])
                    codes.append(lilsf_df.iloc[0]['code'])
                    parents.append(int(lilsf_df.iloc[0]['hypers']))
                next_id = int(lilsf_df.iloc[0]['hypers'])
            if next_id not in ids:
                lilsf_df = semfield_df[semfield_df['id'] == next_id]
                ids.append(next_id)
                labels.append(lilsf_df.iloc[0]['english'])
                codes.append(lilsf_df.iloc[0]['code'])
                parents.append('')

        # This checks to see if WordNet recognizes the word as a noun. If not, it displays an error instead of a graph.
        if word not in greek_nouns:
            graph_title = f'Error: Ancient Greek WordNet does not recognize "{show_word.capitalize()}" as a noun.'
            figure = {'data': [{'type': 'sunburst'}]}
            right_box_1 = [f'No pronunciation data for {show_word}.']
        else:
            graph_title = f'Semantic Domains of "{show_word.capitalize()}"'
            figure = {'data': [{'type': 'sunburst',
                                'ids': ids,
                                'labels': labels,
                                'parents': parents,
                                'hovertext': codes,
                                'hoverinfo': 'text'}],
                      'layout': {'font': {'family': 'Quicksand',
                                          'size': 24},
                                 'margin': {'l': 10,
                                            'r': 10,
                                            'b': 10,
                                            't': 10},
                                 'colorway': ['#03045e', '#023e8a', '#0077b6', '#0096c7', '#00b4d8', '#48cae4',
                                              '#90e0ef', '#ade8f4', '#caf0f8', '#e63946']
                                 }
                      }
            if pd.notna(lillemma.iloc[0]['pronunciation']):
                right_box_1 = [f'{show_word} is pronounced', html.Br(), html.H1(lillemma.iloc[0]['pronunciation'],
                                                                                className='pronunciation')]
            else:
                right_box_1 = [f'No pronuncation data for {show_word}.']

        # Checks if word has been validated.
        if word not in validated_list:
            right_box_2 = ['The definitions of ', html.B(f'{show_word} '), html.Br(),
                           html.B('have not been validated.')]
        else:
            right_box_2 = ['The definitions of ', html.B(f'{show_word}'), html.Br(),
                           html.B('have been validated.')]

        # Checks is word has semfield data.
        if len(base_synsets) == 0:
            right_box_4 = [f'There is no semantic field data on {show_word}.']
        else:
            right_box_4 = ['The noun "', html.B(f'{show_word}'), '" is a member of',
                           html.H1(str(len(base_synsets))),
                           ' outer semfields.']

    return graph_title, figure, right_box_1, right_box_2, box2c, right_box_3, box3c, right_box_4


# This will allow a layout of "impression" to be shown when the page is first loaded.
def initial_layout():
    init_title, init_fig, init_ss_list, init_defs, b2c, init_paths, b3c, init_longest_path = \
        make_dash('impression', 'english')
    return html.Div(className='grid-container',
                    children=[html.Div(className='left-container',
                                       children=[html.Div(className='input-container',
                                                          children=[html.H3(className='input-label',
                                                                            children='Text Input'), html.Br(),
                                                                    dcc.RadioItems(id='language-sel',
                                                                                   className='radio-buttons',
                                                                                   options=[
                                                                                       {'label': 'English',
                                                                                        'value': 'english'},
                                                                                       {'label': 'Ancient Greek',
                                                                                        'value': 'greek'}
                                                                                   ],
                                                                                   value='english'),
                                                                    html.Br(),
                                                                    dcc.Input(id='input-state',
                                                                              type='text',
                                                                              placeholder='Type a noun',
                                                                              debounce=True),
                                                                    html.Button(children='Go', id='start'), html.Br(),
                                                                    html.Button(id='random-button',
                                                                                children='Give Me a Random Word')]
                                                          ),
                                                 html.Div(className='info-container',
                                                          id='info-container',
                                                          children=[html.H3(className='info-head',
                                                                            children='What is this?'),
                                                                    dcc.Markdown(what_string_1), html.Br(),
                                                                    dcc.Markdown(what_string_2), html.Br(),
                                                                    dcc.Markdown(what_string_3), html.Br(),
                                                                    html.H3(className='info-head',
                                                                            children='Why Do This?'),
                                                                    dcc.Markdown(why_string_1), html.Br(),
                                                                    html.H3(className='info-head',
                                                                            children='Who & How?'),
                                                                    dcc.Markdown(how_string_1)
                                                                    ]
                                                          )
                                                 ]
                                       ),
                              html.Div(className='center-container',
                                       children=[html.H3(id='graph-title',
                                                         className='graph-title',
                                                         children=init_title,
                                                         ),
                                                 html.Div(id='graph-box',
                                                          className='graph-box',
                                                          children=dcc.Graph(id='sem-dom-graph',
                                                                             figure=init_fig,
                                                                             config={'scrollZoom': True,
                                                                                     'responsive': True},
                                                                             style={'height': '100%',
                                                                                    'width': '100%'}
                                                                             )
                                                          )
                                                 ]
                                       ),
                              html.Div(className='right-container',
                                       children=[html.Div(id='right-box-1',
                                                          children=init_ss_list,
                                                          className='right-box'),
                                                 html.Div(id='right-box-2',
                                                          children=init_defs,
                                                          className=b2c),
                                                 html.Div(id='right-box-3',
                                                          children=init_paths,
                                                          className=b3c),
                                                 html.Div(id='right-box-4',
                                                          children=init_longest_path,
                                                          className='right-box'),
                                                 html.Div(className='mobile-info',
                                                          id='mobile-info',
                                                          children=[html.H3(className='info-head',
                                                                            children='What is this?'),
                                                                    dcc.Markdown(what_string_1), html.Br(),
                                                                    dcc.Markdown(what_string_2), html.Br(),
                                                                    dcc.Markdown(what_string_3), html.Br(),
                                                                    html.H3(className='info-head',
                                                                            children='Why Do This?'),
                                                                    dcc.Markdown(why_string_1), html.Br(),
                                                                    html.H3(className='info-head',
                                                                            children='Who & How'),
                                                                    dcc.Markdown(how_string_1)
                                                                    ]
                                                          )
                                                 ]
                                       )
                              ]
                    )


with open(os.path.join('application', 'semdoms', 'static', 'english_nouns.json')) as json_file:
    english_nouns = json.load(json_file)

with open(os.path.join('application', 'semdoms', 'static', 'validated_list.json'), encoding='utf-8') as val_file:
    validated_list = json.load(val_file)

with open(os.path.join('application', 'semdoms', 'static', 'pro_words.json'), encoding='utf-8') as pro_file:
    pro_words = json.load(pro_file)

lemma_df = pd.read_csv(os.path.join('application', 'semdoms', 'static', 'lemma.csv'))
greek_nouns = lemma_df['lemma'].to_numpy()
sense_df = pd.read_csv(os.path.join('application', 'semdoms', 'static', 'literalsense.csv'),
                       dtype={'id': int, 'lemma': 'int32', 'synset': 'int32'})
synset_df = pd.read_csv(os.path.join('application', 'semdoms', 'static', 'synset.csv'),
                        dtype={'id': 'int32'})
semfield_df = pd.read_csv(os.path.join('application', 'semdoms', 'static', 'semfield.csv'),
                          dtype={'id': 'int16', 'hypers': 'int16'})

# Construct a default sunburst graph. This prevents flickering when loading.
fig = go.Figure(go.Sunburst())

# Write out markdown text strings that will be used in the app
what_string_1 = '''This is an interactive semantic domains visualizer (click on the graph!). Given an English noun, 
this will display the hierarchy of semantic domains that word falls under according to 
[English WordNet](https://wordnet.princeton.edu/).'''
what_string_2 = '''Semantic domains are categories of meaning which are filled up by words which fit that meaning. This 
page, by default, displays the semantic domains for the word "impression." On the outer edges, you can see the leaf node 
domains that contain the various meanings of the word "impression."'''
what_string_3 = '''These domains are arranged in a hierarchy. An impression can be a depression which is a concave 
shape which is a solid which is a shape and so on until one works their way up to the root node "entity." All nouns are 
eventually entities.'''
why_string_1 = '''I have an interest in applying computational linguistic methods to the New Testament and Ancient 
Greek. Sometimes when explaining what I'm doing, it's helpful to first show the same concept in English. Hence, I made 
this app with an English option. What this does is actually fairly simple because it's just a stepping stone 
along the path to a much more complex semantic preferences project. But I thought it was fun to 
look at in its own right so I shared it here. It also provided an opportunity to solve a deceptively tricky problem 
necessary for properly displaying the semantic domains of the semantic preferences project: WordNet will sometimes 
assign the same synset to multiple hypernyms. The input of this sunburst diagram, however, required that each synset 
have a unique ID (which is displayed upon hovering) with only a single parent. The problem is compounded as multiple 
synsets along a path from a leaf node to a top node may have multiple hypernyms. The number of nodes that require 
unique renaming grows exponentially with each multi-parent node along the same path.'''
how_string_1 = '''I'm [Chris Drymon](https://chrisdrymon.com). I primarily work in Python - this project included. It 
utilizes Princeton's 
[English WordNet](https://wordnet.princeton.edu/) through the [Natural Language Toolkit](https://www.nltk.org/). The 
front end web app was made with [Dash](https://plotly.com/dash/) while the semantic domains visualizations were created 
using [Plotly](https://plotly.com/). It has been deployed on [Heroku's](https://www.heroku.com) free tier (which 
required careful memory management) using the [Green Unicorn WSGI Server](https://gunicorn.org).'''


@semdoms_bp.route('/semdoms', methods=['GET'])
def create_sd_dash(server):
    """Creates the Semantic Domains App Dashboard"""
    # Run the server. This is how we choose what the initially loaded graph will be.
    dash_app = dash.Dash(__name__, server=server, routes_pathname_prefix='/semdoms/')
    dash_app.title = 'Semantic Domains'
    dash_app.layout = initial_layout()

    init_callbacks(dash_app)

    return dash_app.server


def init_callbacks(dash_app):
    @dash_app.callback(
        Output('input-state', 'value'),
        [Input('random-button', 'n_clicks')],
        [State('language-sel', 'value')]
        )
    def random_word(clicks, lang):
        if clicks is None:
            raise PreventUpdate
        else:
            if lang == 'english':
                return random.choice(english_nouns)
            else:
                return random.choice(pro_words)

    @dash_app.callback(
        [Output('graph-title', 'children'),
         Output('sem-dom-graph', 'figure'),
         Output('right-box-1', 'children'),
         Output('right-box-2', 'children'),
         Output('right-box-2', 'className'),
         Output('right-box-3', 'children'),
         Output('right-box-3', 'className'),
         Output('right-box-4', 'children')],
        [Input('input-state', 'value')],
        [State('language-sel', 'value')]
    )
    def update_fig(word, lang):
        return make_dash(word, lang)

    @dash_app.callback(
        [Output('info-container', 'children'),
         Output('mobile-info', 'children')],
        [Input('language-sel', 'value')]
    )
    def change_language(language):
        if language == 'english':
            div = [html.H3(className='info-head',
                           children='What is this?'),
                   dcc.Markdown(what_string_1), html.Br(),
                   dcc.Markdown(what_string_2), html.Br(),
                   dcc.Markdown(what_string_3), html.Br(),
                   html.H3(className='info-head',
                           children='Why Do This?'),
                   dcc.Markdown(why_string_1), html.Br(),
                   html.H3(className='info-head',
                           children='Who & How'),
                   dcc.Markdown(how_string_1)
                   ]
            return div, div
        else:
            div = [html.H5(className='info-head',
                           children=html.H5("Don't know Greek? Type an English word and I'll try to translate "
                                            "it into an Ancient Greek noun!")),
                   html.Br(),
                   dcc.Markdown("""If you are typing a word in Greek and are unsure of the proper accentuation, don't fret! 
                   We will try a series of accentuation patterns if the initial entry is not found. If any entry is still 
                   not found, the app will attempt to look up a lemmatized version of the word."""),
                   html.Br(),
                   dcc.Markdown("""This project relies upon Ancient Greek WordNet which is far from complete. Data 
                   is frequently unavailable. In place of the hierarchy of semantic domains found in English WordNet, 
                   Ancient Greek WordNet offers broad semantic fields which are based on the dewey 
                   decimal system. Additionally, almost none of the definitions of the synsets have been manually 
                   verified for accuracy. In order to quickly create 
                   something functional, a method was devised by which the synsets of modern English words could be 
                   automatically applied to appropriate Ancient Greek words. This was a huge step forward but is prone to 
                   frequent error. One might notice that this app will sometimes return an inordinate number of definitions 
                   for a given Greek word. That is not because Ancient Greek words tend to have a gratuituous number of 
                   possible meanings, but is just a consequence of the imprecision that currently exists in the Ancient 
                   Greek version of WordNet. As progress is made in its construction, these problems will be cleared up. In
                   the meantime, use the unvalidated information with caution.""", dedent=True),
                   html.Br(),
                   dcc.Markdown("""In addition to the resources used to create the English visualization, the Ancient 
                   Greek version uses:"""),
                   html.Br(),
                   dcc.Markdown("""
                   * [Ancient Greek WordNet](https://greekwordnet.chs.harvard.edu/) which is hosted by Harvard's Center 
                   for Hellenistic Studies

                   * [The Classical Language ToolKit](http://cltk.org/) created by Kyle P. Johnson et al.

                   * James Tauber's [Greek Accentuation Library](https://github.com/jtauber/greek-accentuation)""")
                   ]
            return div, div

# dash_app.index_string = '''
# <!DOCTYPE html>
# <html>
#     <head>
#         {%metas%}
#         <title>Semantic Domains</title>
#         {%favicon%}
#         {%css%}
#     </head>
#     <body>
#         {%app_entry%}
#         <footer>
#             {%config%}
#             {%scripts%}
#             {%renderer%}
#         </footer>
#     </body>
# </html>
# '''
