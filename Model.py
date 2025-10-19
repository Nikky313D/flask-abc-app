import pandas as pd
import numpy as np
import xgboost as xgb
import matplotlib.pyplot as plt

ventas = pd.read_csv('ventas.csv')
ventas['Fecha'] = pd.to_datetime(ventas['Fecha'], format='%Y%m%d')

# Seleccionar un SKU para modelar
sku = ventas['Clave'].value_counts().idxmax()
df_sku = ventas[ventas['Clave'] == sku].copy()

# Variables predictoras (puedes agregar más variables)
X = df_sku[['PrecioUnit']].copy()
y = df_sku['Cantidad']

# Entrenar modelo para predecir demanda (ventas unidades)
model = xgb.XGBRegressor(objective='reg:squarederror', random_state=42)
model.fit(X, y)

# Obtener costo promedio para SKU
costo_promedio = df_sku['Costo'].mean()

# Rango de precios para evaluar
min_p = df_sku['PrecioUnit'].min()*0.8
max_p = df_sku['PrecioUnit'].max()*1.2
precios = np.linspace(min_p, max_p, 100)

# Predecir demanda para el rango de precios
demanda_predicha = model.predict(precios.reshape(-1,1))

# Calcular utilidad = (precio - costo) * demanda
utilidad = (precios - costo_promedio) * demanda_predicha

# Precio óptimo máximo de utilidad
indice_optimo = np.argmax(utilidad)
precio_optimo = precios[indice_optimo]
utilidad_maxima = utilidad[indice_optimo]

print(f"Precio óptimo basado en demanda estimada: {precio_optimo:.2f}")
print(f"Utilidad estimada máxima: {utilidad_maxima:.2f}")

# Graficar utilidad vs precio
plt.plot(precios, utilidad, label='Utilidad esperada')
plt.axvline(x=precio_optimo, color='r', linestyle='--', label='Precio óptimo')
plt.xlabel('Precio')
plt.ylabel('Utilidad')
plt.title(f'Optimización de precio para SKU {sku}')
plt.legend()
plt.show()
