import os
import pickle
import logging
import numpy as np
import pandas as pd
from umap import UMAP
from hdbscan import HDBSCAN
from bertopic import BERTopic
from ..config import SAVE_DIR
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import CountVectorizer
from .utils import get_visualize_hierarchy, get_3d_time_plot, create_two_treemaps

logger = logging.getLogger(__name__)


def initialize_models(len_docs, embedding_model_name="BAAI/bge-large-en-v1.5"):
    """Initializes and returns sentence transformer and BERTopic models along with sub-models."""
    sentence_model = SentenceTransformer(embedding_model_name)
    vectorizer = CountVectorizer(stop_words="english")
    if len_docs < 100:
        umap_model = UMAP(n_neighbors=5, n_components=5, min_dist=0.0, metric='cosine', random_state=42)
        hdbscan_model = HDBSCAN(min_cluster_size=2, min_samples=2, metric='euclidean', cluster_selection_method='eom')
    elif len_docs < 300:
        umap_model = UMAP(n_neighbors=5, n_components=5, min_dist=0.0, metric='cosine', random_state=42)
        hdbscan_model = HDBSCAN(min_cluster_size=3, min_samples=3, metric='euclidean', cluster_selection_method='eom')
    elif len_docs < 400:
        umap_model = UMAP(n_neighbors=5, n_components=5, min_dist=0.0, metric='cosine', random_state=42)
        hdbscan_model = HDBSCAN(min_cluster_size=6, min_samples=6, metric='euclidean', cluster_selection_method='eom')
    else:
        umap_model = UMAP(n_neighbors=5, n_components=5, min_dist=0.0, metric='cosine', random_state=42)
        hdbscan_model = HDBSCAN(min_cluster_size=8, min_samples=8, metric='euclidean', cluster_selection_method='eom')
    topic_model = BERTopic(embedding_model=sentence_model, umap_model=umap_model, hdbscan_model=hdbscan_model, vectorizer_model=vectorizer)
    logging.info("Models initialized successfully.")
    return sentence_model, topic_model

def generate_embeddings(sentence_model, docs):
    """Encodes documents into embeddings."""
    logging.debug("Generating embeddings for documents.")
    embeddings = []
    for doc in docs:
        embedding = get_embedding_per_doc(sentence_model, doc)
        embeddings.append(embedding)
    return np.array(embeddings)
    
def batch_generate_embeddings(sentence_model, docs):
    logging.debug("Generating embeddings for documents in batches.")
    try:
        embeddings = sentence_model.encode(docs)
        logging.debug("Embeddings generated successfully.")
        return embeddings
    except Exception as e:
        logging.error(f"Error generating embeddings: {e}")
        raise
    
    
def get_embedding_per_doc(sentence_model, doc):
    """Encodes a single document into an embedding."""
    logging.debug("Generating embeddings for a single document.")
    try:
        embedding = sentence_model.encode([doc])
        logging.debug("Embeddings generated successfully.")
        return embedding[0]
    except Exception as e:
        logging.error(f"Error generating embeddings: {e}")
        raise

def train_topic_model(topic_model, docs, embeddings):
    """Fits the topic model with the documents and embeddings."""
    logging.info("Starting to train the topic model.")
    try:
        topic_model.fit(docs, embeddings)
        logging.info("Topic model training completed.")
    except Exception as e:
        logging.error(f"Error training topic model: {e}")
        raise

def save_and_visualize(topic_model, docs, df, embedding_model = "BAAI/bge-large-en-v1.5"):
    """Saves the topic model and generates visualizations."""
    logging.info("Starting to save the topic model and generate visualizations.")
    
    images_dir = SAVE_DIR["TOPIC_MODEL_IMAGE_DIR"]
    data_dir = SAVE_DIR["CSV_DATA_DIR"]
    model_dir = SAVE_DIR["TOPIC_MODEL_DIR"]
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(model_dir, exist_ok=True)
    
    try:
        df['topic'] = topic_model.topics_
        num_topics = min(len(topic_model.get_topics()), 16)
        fig1 = topic_model.visualize_barchart(topics=[i for i in range(0, num_topics)]).to_json()
        with open(os.path.join(images_dir, "barchart.json"), "w") as f:
            f.write(fig1)
        logging.debug("Barchart visualization saved.")
        
        fig2 = topic_model.visualize_topics(width=1000, height=1000).to_json()
        with open(os.path.join(images_dir, "topics.json"), "w") as f:
            f.write(fig2)
        logging.debug("Topics visualization saved.")
        
        fig3 = topic_model.visualize_documents(df['Title'].tolist()).to_json()
        with open(os.path.join(images_dir, "documents.json"), "w") as f:
            f.write(fig3)
        logging.debug("Documents visualization saved.")
        
        
        topics_over_time = topic_model.topics_over_time(docs, df['Timestamp'].tolist(), nr_bins=20)
        fig4 = topic_model.visualize_topics_over_time(topics_over_time).to_json()
        with open(os.path.join(images_dir, "topics_over_time.json"), "w") as f:
            f.write(fig4)
        logging.debug("Topics over time visualization saved.")
        
        hierarchical_topics = topic_model.hierarchical_topics(docs)
        fig5 = get_visualize_hierarchy(topic_model = topic_model, hierarchical_topics=hierarchical_topics, orientation="bottom", width=3000, height=600).to_json()
        tree = topic_model.get_topic_tree(hierarchical_topics)
        with open(os.path.join(images_dir, "hierarchy.json"), "w") as f:
            f.write(fig5)
        with open(os.path.join(images_dir, "topic_tree.txt"), "w") as f:
            f.write(tree)
            
        logging.debug("Hierarchy visualization saved.")
        
        fig6 = get_3d_time_plot(topics_over_time)
        with open(os.path.join(images_dir, "3d_time_plot.pkl"), 'wb') as f:
            pickle.dump(fig6, f)
        
        logging.debug("3D time plot visualization saved.")
        
        fig7 = create_two_treemaps(df)
        with open(os.path.join(images_dir, "treemap.pkl"), 'wb') as f:
            pickle.dump(fig7, f)
            
        logging.debug("Treemap visualization saved.")
        
        logging.info("All visualizations generated and saved.")
        
        topic_model.save(os.path.join(model_dir, "topic_model"), serialization="safetensors", save_ctfidf=True, save_embedding_model=embedding_model)
        logging.debug("Topic model saved successfully.")
        df.to_csv(os.path.join(data_dir, "df_with_response_and_topics.csv"), index=False)
        logging.debug("Dataframe with topics saved.")

    except Exception as e:
        logging.error(f"Error saving topic model: {e}")
        raise
   
def compute_topic_modeling(df, embedding_model_name="BAAI/bge-large-en-v1.5", column_name="RelevantKeywords"):
    try:
        df = df.dropna(subset=[column_name])
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='ISO8601')
        docs = df[column_name].tolist()
        len_docs = len(docs)
        sentence_model, topic_model = initialize_models(len_docs, embedding_model_name)
        embeddings = batch_generate_embeddings(sentence_model, docs)
        train_topic_model(topic_model, docs, embeddings)
        save_and_visualize(topic_model, docs, df, embedding_model=embedding_model_name)
    except Exception as e:
        logging.error(f"Error during topic modeling: {e}")
        raise
