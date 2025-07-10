import streamlit as st
from lida import Manager, TextGenerationConfig, llm
from lida.datamodel import Goal
import os
import pandas as pd
from PIL import Image
import io
import base64
from dotenv import load_dotenv
from authentication import init_authentication  
from llama_index.core.readers import SimpleDirectoryReader
from llama_index.core import Settings
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.readers.file import PagedCSVReader
from llama_index.vector_stores.faiss import FaissVectorStore
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core import VectorStoreIndex
import faiss
import os
import pandas as pd


load_dotenv()


# import libraries here

if not st.session_state.authentication_status:
    st.info('Please Login from the Home page and try again.')
    st.stop()

# rest of the operations


EMBED_DIMENSION=3072
Settings.llm = OpenAI(model="gpt-4o-mini")
Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-large", dimensions=EMBED_DIMENSION)


import streamlit_analytics2 as streamlit_analytics
streamlit_analytics.start_tracking(load_from_json="streamlit_analytics_csv.json")

# make data dir if it doesn't exist
os.makedirs("data", exist_ok=True)
CSV_DIR = "/home/s07rb2/github/D4NZ/data/csv"

csv_files = [f for f in os.listdir(CSV_DIR) if f.endswith('.csv')]
st.set_page_config(
    page_title="CSV VIZ and Q&A",
    page_icon="📊",
)

# auth = init_authentication()
# if not auth.is_authenticated():
#     auth.login_form()
#     st.stop()

# # Check authentication
# if not auth.login_form():
#     st.stop()


st.write("# CSV-VIZ 📊")



# Step 1 - Get OpenAI API key
openai_key = os.getenv("OPENAI_API_KEY")

# st.markdown(
#     """
#     LIDA is a library for generating data visualizations and data-faithful infographics.
#     LIDA is grammar agnostic (will work with any programming language and visualization
#     libraries e.g. matplotlib, seaborn, altair, d3 etc) and works with multiple large language
#     model providers (OpenAI, Azure OpenAI, PaLM, Cohere, Huggingface). Details on the components
#     of LIDA are described in the [paper here](https://arxiv.org/abs/2303.02927) and in this
#     tutorial [notebook](notebooks/tutorial.ipynb). See the project page [here](https://microsoft.github.io/lida/) for updates!.

#    This demo shows how to use the LIDA python api with Streamlit. [More](/about).

#    ----
# """)

# Step 2 - Select a dataset and summarization method
if openai_key:
    # Initialize selected_dataset to None
    selected_dataset = None

    # select model from gpt-4 , gpt-3.5-turbo, gpt-3.5-turbo-16k
    selected_model = "gpt-4o-mini"

    temperature = 0.0

    use_cache = True

    # Handle dataset selection and upload
    # st.sidebar.write("### Choose a dataset")
    csv_files = [f for f in os.listdir(CSV_DIR) if f.endswith('.csv')]

    datasets = [{"label": "Select a dataset", "url": None}]
    for csv_file in csv_files:
        file_path = os.path.join(CSV_DIR, csv_file)
        file_name = os.path.splitext(csv_file)[0]
        datasets.append({"label": file_name, "url": file_path})

    selected_dataset_label = st.selectbox(
        'Choose a dataset',
        options=[dataset["label"] for dataset in datasets],
        index=0
    )

    upload_own_data = st.checkbox("Upload your own data", value=False)
    # own_goal = st.checkbox("Add Your Own question")
    # upload_own_data = True
    if upload_own_data:
        uploaded_file = st.sidebar.file_uploader("Choose a CSV or JSON file", type=["csv", "json"])

        if uploaded_file is not None:
            # Get the original file name and extension
            file_name, file_extension = os.path.splitext(uploaded_file.name)

            # Load the data depending on the file type
            if file_extension.lower() == ".csv":
                data = pd.read_csv(uploaded_file)
            elif file_extension.lower() == ".json":
                data = pd.read_json(uploaded_file)

            # Save the data using the original file name in the data dir
            uploaded_file_path = os.path.join("data", uploaded_file.name)
            data.to_csv(uploaded_file_path, index=False)

            selected_dataset = uploaded_file_path

            datasets.append({"label": file_name, "url": uploaded_file_path})

            # st.sidebar.write("Uploaded file path: ", uploaded_file_path)
    else:
        selected_dataset = datasets[[dataset["label"]
                                     for dataset in datasets].index(selected_dataset_label)]["url"]

    if not selected_dataset:
        st.info("To continue, select a dataset from the sidebar on the left or upload your own.")

    # st.sidebar.write("### Choose a summarization method")
    # # summarization_methods = ["default", "llm", "columns"]
    summarization_methods = [
        {"label": "llm",
         "description":
         "Uses the LLM to generate annotate the default summary, adding details such as semantic types for columns and dataset description"},
        {"label": "default",
         "description": "Uses dataset column statistics and column names as the summary"},

        {"label": "columns", "description": "Uses the dataset column names as the summary"}]

    # # selected_method = st.sidebar.selectbox("Choose a method", options=summarization_methods)
    # selected_method_label = st.sidebar.selectbox(
    #     'Choose a method',
    #     options=[method["label"] for method in summarization_methods],
    #     index=0
    # )
    selected_method_label = "llm"
    selected_method = summarization_methods[[method["label"]
                                             for method in summarization_methods].index(selected_method_label)]

    # add description of selected method in very small font to sidebar
    selected_summary_method_description = summarization_methods[[
        method["label"] for method in summarization_methods].index(selected_method_label)]["description"]

    # if selected_method:
    #     st.sidebar.markdown(
    #         f"<span> {selected_summary_method_description} </span>",
    #         unsafe_allow_html=True)

# Step 3 - Generate data summary
if openai_key and selected_dataset and selected_method:
    lida = Manager(text_gen=llm("openai", api_key=openai_key))
    textgen_config = TextGenerationConfig(
        n=1,
        temperature=temperature,
        model=selected_model,
        use_cache=use_cache)

    # **** lida.summarize *****
    summary = lida.summarize(
        selected_dataset,
        summary_method=selected_method,
        textgen_config=textgen_config)

    with st.expander("Summary of the Dataset"):
        if "fields" in summary:
            fields = summary["fields"]
            nfields = []
            for field in fields:
                flatted_fields = {}
                flatted_fields["column"] = field["column"]
                # flatted_fields["dtype"] = field["dtype"]
                for row in field["properties"].keys():
                    if row != "samples":
                        flatted_fields[row] = field["properties"][row]
                    else:
                        flatted_fields[row] = str(field["properties"][row])
                # flatted_fields = {**flatted_fields, **field["properties"]}
                nfields.append(flatted_fields)
            nfields_df = pd.DataFrame(nfields)
            st.write(nfields_df)
        else:
            st.write(str(summary))

    # Step 4 - Generate goals
    if summary:
        num_goals = 10
        
        # **** lida.goals *****
        goals = lida.goals(summary, n=num_goals, textgen_config=textgen_config)
        st.write(f"## Question ({len(goals)})")

        default_goal = goals[0].question
        goal_questions = [goal.question for goal in goals]


        combined_questions = ["Write your own question..."] + goal_questions
        selected_option = st.selectbox('Select or write a question', options=combined_questions, index=0)

        if selected_option == "Write your own question...":
            user_goal = st.text_input("Enter your question", value=default_goal)
            if user_goal:
                new_goal = Goal(question=user_goal, visualization=user_goal, rationale="")
                goals.append(new_goal)
                goal_questions.append(user_goal)
                selected_goal = user_goal
        else:
            selected_goal = selected_option

        selected_goal_index = goal_questions.index(selected_goal)
        
        selected_goal_object = goals[selected_goal_index]

        # Step 5 - Generate visualizations
        if selected_goal_object:
            selected_library = "seaborn"

            # Update the visualization generation call to use the selected library.
            st.write("## Visualizations")

            num_visualizations = 2
            textgen_config = TextGenerationConfig(
                n=num_visualizations, temperature=temperature,
                model=selected_model,
                use_cache=use_cache)

            # **** lida.visualize *****
            visualizations = lida.visualize(
                summary=summary,
                goal=selected_goal_object,
                textgen_config=textgen_config,
                library=selected_library)

            viz_titles = [f'Visualization {i+1}' for i in range(len(visualizations))]

            selected_viz_title = st.selectbox('Choose a visualization', options=viz_titles, index=0)

            selected_viz = visualizations[viz_titles.index(selected_viz_title)]

            if selected_viz.raster:
                
                imgdata = base64.b64decode(selected_viz.raster)
                img = Image.open(io.BytesIO(imgdata))
                st.image(img, caption=selected_viz_title)

            with st.expander("Python Visualization Code"):
                st.code(selected_viz.code)

streamlit_analytics.stop_tracking()