# # xception model    
import tensorflow as tf
from tensorflow.keras.applications.xception import Xception, preprocess_input # type: ignore
from tensorflow.keras.preprocessing import image # type: ignore
from tensorflow.keras.models import Model # type: ignore
import numpy as np
import time

base_model = Xception(weights='imagenet')
model = Model(inputs=base_model.input, outputs=base_model.layers[-2].output)

def preprocess_image(img):
    start_time = time.time()
    # img = img.resize((299, 299))  # Resize the image
    img_data = image.img_to_array(img)
    img_data = np.expand_dims(img_data, axis=0)
    img_data = preprocess_input(img_data)
    end_time = time.time()
    preprocessing_time = end_time - start_time
    print(f"Image preprocessing time: {preprocessing_time:.2f} seconds")
    return img_data

def get_embeddings(img):
    img_data = preprocess_image(img)
    start_time = time.time()
    embeddings = model.predict(img_data)
    end_time = time.time()
    prediction_time = end_time - start_time
    print(f"Embedding time: {prediction_time:.2f} seconds")
    return embeddings.flatten().tolist()






# # ResNet50 model                       ## similar results as the xception model , if this is used then change image size value to 224,224
# import tensorflow as tf
# from tensorflow.keras.applications.resnet50 import ResNet50, preprocess_input
# from tensorflow.keras.preprocessing import image
# from tensorflow.keras.models import Model
# import numpy as np
# import time

# base_model = ResNet50(weights='imagenet', include_top=False, pooling='avg')
# model = Model(inputs=base_model.input, outputs=base_model.output)

# def preprocess_image(img):
#     start_time = time.time()
#     # img = img.resize((224, 224))  
#     img_data = image.img_to_array(img)
#     img_data = np.expand_dims(img_data, axis=0)
#     img_data = preprocess_input(img_data)
#     end_time = time.time()
#     preprocessing_time = end_time - start_time
#     print(f"Image preprocessing time: {preprocessing_time:.2f} seconds")
#     return img_data

# def get_embeddings(img):
#     img_data = preprocess_image(img)
#     start_time = time.time()
#     embeddings = model.predict(img_data)
#     end_time = time.time()
#     prediction_time = end_time - start_time
#     print(f"Embedding time: {prediction_time:.2f} seconds")
#     return embeddings.flatten().tolist()








# # # # EfficientNetB7 model               ## used this to filter ccording to catgoery buapproach didnt work
# import tensorflow as tf
# from tensorflow.keras.applications.efficientnet import EfficientNetB7, preprocess_input, decode_predictions
# from tensorflow.keras.preprocessing import image
# import numpy as np
# import time
# from PIL import Image


# model = EfficientNetB7(weights='imagenet')

# def preprocess_image(img):
#     start_time = time.time()
#     #img = img.resize((600, 600))  # Resize the image to 600x600 for EfficientNetB7
#     img_data = image.img_to_array(img)
#     img_data = np.expand_dims(img_data, axis=0)
#     img_data = preprocess_input(img_data)
#     end_time = time.time()
#     preprocessing_time = end_time - start_time
#     print(f"Image preprocessing time: {preprocessing_time:.2f} seconds")
#     return img_data

# def get_embeddings_and_predictions(img):
#     img_data = preprocess_image(img)
#     start_time = time.time()
#     predictions = model.predict(img_data)
#     end_time = time.time()
#     prediction_time = end_time - start_time
#     print(f"Prediction time: {prediction_time:.2f} seconds")
    
#     # Decode predictions
#     decoded_predictions = decode_predictions(predictions, top=4)[0]
#     top_categories = [(pred[1], pred[2]) for pred in decoded_predictions]  # (class_name, probability)
    
#     # Extract embeddings from the last layer's output
#     embeddings = predictions.flatten().tolist()
#     formatted_predictions = ', '.join([label for label, score in top_categories])
#     formatted_predictions_no_spaces = formatted_predictions.replace(' ', '')
#     return embeddings, formatted_predictions_no_spaces


