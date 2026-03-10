
import pandas as pd
from tqdm import trange
import os

knowladge = pd.read_csv('Disease.csv',names=['header','relation','tail'])
disease = pd.read_pickle('disease.pk')
diseases = pd.read_pickle('diseases.pk')
symptom = pd.read_pickle('symptom.pk')
symptoms =  pd.read_pickle('symptoms.pk')
kg = pd.read_pickle('kg.pk')
kgs =  pd.read_pickle('kgs.pk')
data = pd.read_csv('medical.csv')

def get_entity(sen,li,lis):
    ej = False
    entity = []
    for i in li:
        if i in sen:
            entity.append(i)
    l = list(set(entity))
    if l == []:
        ej = True
        for i in li:
            for i2 in lis[i]:
                if i2 in sen:
                    entity.append(i)
        l = list(set(entity))
    return l,ej


l = '医生你好，我拉肚子严重怎么办？'

def know(sen,step,entity):

    if step == 0:
        disease_entity, diseases_ej = get_entity(sen, disease, diseases)
        symptom_entity, symptom_ej = get_entity(sen, symptom, symptoms)
        if diseases_ej == False:
            entity['disease'].extend(disease_entity)
        if disease_entity == symptom_entity == []:
            return [], entity
        if disease_entity!=[]:
            symptomitem = list(knowladge.loc[(knowladge['header'] == disease_entity[0] + '[疾病]') & (knowladge['relation'] == '症状')]['tail'])
            if len(symptomitem)!=0:

                entity['symptom'].extend(symptomitem[:2])
                return symptomitem[:2],entity
            else:
                if len(symptom_entity)!=0:
                    entity['disease'].extend(disease_entity)
                    entity['symptom'].extend(symptom_entity[:2])
                    return symptom_entity[:2], entity
                else:
                    return [], entity
        else:
            if len(symptom_entity) != 0:
                entity['symptom'].extend(symptom_entity[:2])
                return symptom_entity[:2], entity
            else:
                return [], entity
    elif step == 1:
        kg_entity, kg_ej = get_entity(sen, kg, kgs)
        if kg_ej == False:
            entity['disease'].extend(kg_entity)
        if kg_entity == kg_entity == []:
            return [], entity
        if kg_entity != []:
            check = eval(data.loc[data['name'] == kg_entity[0]].iloc[0]['check'])[:2]
            if len(check) != 0:
                entity['check'].extend(check)
                return check, entity
            else:
                return [], entity
        else:
            return [], entity
    elif step == 2:
        kg_entity, kg_ej = get_entity(sen, kg, kgs)
        if kg_ej == False:
            entity['disease'].extend(kg_entity)
        if kg_entity == kg_entity == []:
            return [], entity
        if kg_entity != []:
            recommand_drug = eval(data.loc[data['name'] == kg_entity[0]].iloc[0]['recommand_drug'])[:2]
            if len(recommand_drug) != 0:
                entity['recommand_drug'].extend(recommand_drug)
                return recommand_drug, entity
            else:
                return [], entity
        else:
            return [], entity
    else:
        return [], entity

