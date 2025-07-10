import dash
from dash import html, dcc
import plotly.graph_objects as go
from dash.dependencies import Input, Output
import numpy as np
import pandas as pd
import colorsys

# Initialize Dash
app = dash.Dash(__name__)

# Helper function to generate colors
def generate_colors(n):
    colors = []
    for i in range(n):
        hue = i / n
        saturation = 0.7
        value = 0.9
        rgb = colorsys.hsv_to_rgb(hue, saturation, value)
        colors.append(f'rgb({int(rgb[0]*255)}, {int(rgb[1]*255)}, {int(rgb[2]*255)})')
    return colors

# Sample hierarchical data
def create_sample_data():
    data = {
        'id': ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'],
        'parent': ['', '0', '0', '0', '1', '1', '2', '2', '3', '3', '4', '5', '6'],
        'name': [
            'Root',
            'World Cup',
            'Players',
            'Teams',
            'Goals',
            'Penalties',
            'Messi',
            'Mbappe',
            'Argentina',
            'France',
            'Final Match',
            'Shootout',
            'Performance'
        ],
        'value': [100, 80, 70, 60, 50, 45, 40, 35, 30, 25, 20, 15, 10]
    }
    return pd.DataFrame(data)

# Create the radial tree visualization
def create_radial_tree(df, selected_node=None):
    # Generate colors
    colors = generate_colors(len(df))
    
    # Create figure
    fig = go.Figure(go.Sunburst(
        ids=df['id'],
        labels=df['name'],
        parents=df['parent'],
        values=df['value'],
        branchvalues='total',
        marker=dict(
            colors=colors,
            line=dict(color='white', width=1)
        ),
        hovertemplate="""
        Name: %{label}<br>
        Value: %{value}<br>
        <extra></extra>
        """,
        maxdepth=3  # Limit the displayed depth
    ))
    
    # Update layout
    fig.update_layout(
        width=800,
        height=800,
        title={
            'text': "FuncTree2-style Hierarchical Visualization",
            'y': 0.95,
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top',
            'font': dict(size=20)
        },
        margin=dict(t=100, l=0, r=0, b=0),
        uniformtext=dict(minsize=10, mode='hide'),
        # Add custom background and styling
        paper_bgcolor='rgb(250, 250, 250)',
        plot_bgcolor='rgb(250, 250, 250)',
    )
    
    return fig

# Create sample data
df = create_sample_data()

# App layout
app.layout = html.Div([
    html.Div([
        # Main visualization
        dcc.Graph(
            id='radial-tree',
            figure=create_radial_tree(df),
            style={'width': '800px', 'height': '800px'}
        ),
    ], style={'display': 'flex', 'justifyContent': 'center'}),
    
    # Information panel
    html.Div([
        html.H3("Node Information", style={'textAlign': 'center'}),
        html.Div(id='click-data', style={'margin': '20px'})
    ], style={'width': '80%', 'margin': '0 auto'}),
    
    # Controls
    html.Div([
        html.H3("Visualization Controls", style={'textAlign': 'center'}),
        dcc.Checklist(
            id='display-options',
            options=[
                {'label': ' Show Values', 'value': 'show_values'},
                {'label': ' Show Full Path', 'value': 'show_path'}
            ],
            value=['show_values'],
            style={'margin': '20px'}
        ),
        html.Div([
            html.Label("Color Scheme:"),
            dcc.Dropdown(
                id='color-scheme',
                options=[
                    {'label': 'Default', 'value': 'default'},
                    {'label': 'Sequential', 'value': 'sequential'},
                    {'label': 'Categorical', 'value': 'categorical'}
                ],
                value='default',
                style={'width': '200px', 'margin': '10px'}
            )
        ])
    ], style={'width': '80%', 'margin': '20px auto'})
])

# Callback for click events
@app.callback(
    Output('click-data', 'children'),
    Input('radial-tree', 'clickData')
)
def display_click_data(clickData):
    if not clickData:
        return "Click on a node to see its details"
    
    point = clickData['points'][0]
    node_info = df[df['name'] == point['label']].iloc[0]
    
    return html.Div([
        html.P(f"Selected Node: {point['label']}"),
        html.P(f"Value: {point['value']}"),
        html.P(f"Parent: {node_info['parent'] if node_info['parent'] else 'Root'}"),
        html.P(f"Number of children: {len(df[df['parent'] == node_info['id']])}")
    ])

# Callback for visualization controls
@app.callback(
    Output('radial-tree', 'figure'),
    [Input('display-options', 'value'),
     Input('color-scheme', 'value')]
)
def update_visualization(display_options, color_scheme):
    show_values = 'show_values' in display_options
    show_path = 'show_path' in display_options
    
    # Create updated figure
    fig = create_radial_tree(df)
    
    # Update based on display options
    if not show_values:
        fig.update_traces(text=[''] * len(df))
    
    # Update color scheme
    if color_scheme == 'sequential':
        colors = [f'hsl(200, 50%, {i}%)' for i in range(20, 80, 5)]
        fig.update_traces(marker_colors=colors[:len(df)])
    elif color_scheme == 'categorical':
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                 '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
        fig.update_traces(marker_colors=colors[:len(df)])
    
    return fig

if __name__ == '__main__':
    app.run_server(debug=True)