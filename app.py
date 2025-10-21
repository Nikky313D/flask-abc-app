from flask import Flask, request, render_template_string, send_file, url_for
import pandas as pd
import io
import matplotlib.pyplot as plt
import base64
import os
import random
import matplotlib.dates as mdates

app = Flask(__name__)

HTML = '''
<!doctype html>
<title>Clasificacion ABC</title>
<h1>Clasificacion ABC</h1>
<h2>Sube tu archivo CSV</h2>
<p>El archivo CSV debe contener al menos estas columnas:</p>
<ul>
  <li><b>Clave</b></li>
  <li><b>Total</b></li>
  <li><b>Cantidad</b></li>
  <li><b>Des</b> (Descripción)</li>
  <li><b>Linea</b></li>
  <li><b>Fecha</b> (formato aaaammdd)</li>
  <li><b>PrecioUnit</b> (precio unitario)</li>
  <li><b>Margen</b> (margen unitario o total)</li>
  <li><b>Costo</b> (costo unitario)</li>
</ul>
<form method=post enctype=multipart/form-data>
  <input type=file name=file>
  <input type=submit value=Procesar>
</form>
{% if img_html %}
  <h2>Gráfico de artículos por categoría ABC</h2>
  {{ img_html|safe }}
{% endif %}
{% if extra_chart_html %}
  <h2>Gráficos diarios - artículo aleatorio clase A</h2>
  {{ extra_chart_html|safe }}
{% endif %}
<br><br>
{% if download_link %}
  <a href="{{ download_link }}"><button>Descargar Excel procesado</button></a>
{% endif %}
'''

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    img_html = ''
    extra_chart_html = ''
    download_link = ''
    if request.method == 'POST':
        file = request.files['file']
        if not file:
            return "No se subió ningún archivo"
        ventas = pd.read_csv(file)

        # Convertir columna Fecha con formato aaaammdd
        if 'Fecha' in ventas.columns:
            ventas['Fecha'] = pd.to_datetime(ventas['Fecha'], format='%Y%m%d')

        # Clasificación ABC
        df_abc = ventas.groupby('Clave').agg({
            'Total': 'sum',
            'Cantidad': 'sum',
            'Des': 'first',
            'Linea': 'first'
        }).reset_index()
        df_abc = df_abc.sort_values('Total', ascending=False)
        df_abc['%_individual'] = df_abc['Total'] / df_abc['Total'].sum()
        df_abc['%_acumulado'] = df_abc['Total'].cumsum() / df_abc['Total'].sum()

        def clasifica_abc(p):
            if p <= 0.8:
                return 'A'
            elif p <= 0.95:
                return 'B'
            else:
                return 'C'
        df_abc['ABC'] = df_abc['%_acumulado'].apply(clasifica_abc)

        # Precio mínimo y cantidad total vendida a ese precio
        precio_min = ventas.groupby('Clave').agg({'PrecioUnit': 'min'}).reset_index()
        cantidad_max_pmin = ventas.groupby(['Clave', 'PrecioUnit']).agg({'Cantidad': 'sum'}).reset_index()
        cantidad_max_pmin = cantidad_max_pmin.merge(precio_min, on=['Clave', 'PrecioUnit'])
        cantidad_max_pmin = cantidad_max_pmin[['Clave', 'PrecioUnit', 'Cantidad']].rename(columns={
            'PrecioUnit': 'PrecioMinimo', 'Cantidad': 'CantidadVendidaMin'
        })

        # Precio máximo y cantidad total vendida a ese precio
        precio_max = ventas.groupby('Clave').agg({'PrecioUnit': 'max'}).reset_index()
        cantidad_max_pmax = ventas.groupby(['Clave', 'PrecioUnit']).agg({'Cantidad': 'sum'}).reset_index()
        cantidad_max_pmax = cantidad_max_pmax.merge(precio_max, on=['Clave', 'PrecioUnit'])
        cantidad_max_pmax = cantidad_max_pmax[['Clave', 'PrecioUnit', 'Cantidad']].rename(columns={
            'PrecioUnit': 'PrecioMaximo', 'Cantidad': 'CantidadVendidaMax'
        })

        # Calcular margen total (margen unitario por cantidad)
        ventas['MargenTotal'] = ventas['Margen'] * ventas['Cantidad']

        # Margen total vendido a precio mínimo
        margen_min = ventas.groupby(['Clave', 'PrecioUnit']).agg({'MargenTotal': 'sum'}).reset_index()
        margen_min = margen_min.merge(precio_min, on=['Clave', 'PrecioUnit'])
        margen_min = margen_min.rename(columns={'MargenTotal': 'MargenTotalMin'})

        # Margen total vendido a precio máximo
        margen_max = ventas.groupby(['Clave', 'PrecioUnit']).agg({'MargenTotal': 'sum'}).reset_index()
        margen_max = margen_max.merge(precio_max, on=['Clave', 'PrecioUnit'])
        margen_max = margen_max.rename(columns={'MargenTotal': 'MargenTotalMax'})

        # Combinar márgenes mínimos y máximos
        margenes = margen_min[['Clave', 'PrecioUnit', 'MargenTotalMin']].merge(
            margen_max[['Clave', 'PrecioUnit', 'MargenTotalMax']],
            on='Clave',
            suffixes=('_Min', '_Max')
        )

        # Merge cantidades para calcular % margen
        margenes = margenes.merge(cantidad_max_pmin[['Clave', 'CantidadVendidaMin']], on='Clave')
        margenes = margenes.merge(cantidad_max_pmax[['Clave', 'CantidadVendidaMax']], on='Clave')

        # Calcular % margen mínimo y máximo
        margenes['PctMargenMin'] = margenes['MargenTotalMin'] / (
            margenes['PrecioUnit_Min'] * margenes['CantidadVendidaMin'])
        margenes['PctMargenMax'] = margenes['MargenTotalMax'] / (
            margenes['PrecioUnit_Max'] * margenes['CantidadVendidaMax'])

        # Calculo costo promedio mínimo y máximo (agregado)
        if 'Costo' in ventas.columns:
            costos_promedio = ventas.groupby(['Clave', 'PrecioUnit']).agg({'Costo':'mean'}).reset_index()

            cto_prom_min = costos_promedio.merge(precio_min, on=['Clave','PrecioUnit'])
            cto_prom_min = cto_prom_min[['Clave','Costo']].rename(columns={'Costo':'cto_prom_minimo'})

            cto_prom_max = costos_promedio.merge(precio_max, on=['Clave','PrecioUnit'])
            cto_prom_max = cto_prom_max[['Clave','Costo']].rename(columns={'Costo':'cto_prom_maximo'})
        else:
            cto_prom_min = pd.DataFrame(columns=['Clave','cto_prom_minimo'])
            cto_prom_max = pd.DataFrame(columns=['Clave','cto_prom_maximo'])

        detalle = df_abc[['Clave','Des','Linea','ABC','Cantidad','Total','%_individual','%_acumulado']]
        detalle = detalle.merge(cantidad_max_pmin, on='Clave', how='left')
        detalle = detalle.merge(cantidad_max_pmax, on='Clave', how='left')
        detalle = detalle.merge(margenes[['Clave','PctMargenMin','PctMargenMax']], on='Clave', how='left')
        detalle = detalle.merge(cto_prom_min, on='Clave', how='left')
        detalle = detalle.merge(cto_prom_max, on='Clave', how='left')

        # Guardar excel con 4 hojas
        excel_path = 'resultado_abc.xlsx'
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            for clase in ['A','B','C']:
                df_temp = df_abc[df_abc['ABC']==clase]
                df_temp.to_excel(writer, sheet_name=clase,index=False)
                workbook = writer.book
                worksheet = writer.sheets[clase]
                porcentaje_fmt = workbook.add_format({'num_format':'0.00%'})
                worksheet.set_column(5,6,12,porcentaje_fmt)
            detalle.to_excel(writer, sheet_name='Todos',index=False)
            worksheet4 = writer.sheets['Todos']
            worksheet4.set_column('H:I',15)
            porcentaje_fmt = workbook.add_format({'num_format':'0.00%'})
            worksheet4.set_column('J:K',12,porcentaje_fmt)
            worksheet4.set_column('L:M',15)

        # Gráfico clasificación ABC
        conteo = df_abc['ABC'].value_counts().reindex(['A','B','C']).fillna(0)
        plt.figure(figsize=(6,4))
        conteo.plot(kind='bar',color=['green','orange','red'])
        plt.title('Artículos por categoría ABC')
        plt.xlabel('Categoría')
        plt.ylabel('Cantidad')
        plt.tight_layout()

        img = io.BytesIO()
        plt.savefig(img, format='png')
        plt.close()
        img.seek(0)
        img_b64 = base64.b64encode(img.getvalue()).decode()
        img_html = f'<img src="data:image/png;base64,{img_b64}"/>'

        # Gráficos diarios con línea por mes para artículo aleatorio clase A
        if 'Fecha' in ventas.columns:
            articulos_A = df_abc[df_abc['ABC']=='A']['Clave'].tolist()
            if articulos_A:
                articulo_aleatorio = random.choice(articulos_A)
            else:
                articulo_aleatorio = random.choice(df_abc['Clave'].tolist())

            ventas_art = ventas[ventas['Clave']==articulo_aleatorio].copy()
            ventas_art['YearMonth'] = ventas_art['Fecha'].dt.to_period('M')

            meses = ventas_art['YearMonth'].unique()
            colors = plt.cm.get_cmap('tab10', len(meses))

            # Gráfico ingresos diarios
            plt.figure(figsize=(8,3))
            for i, mes in enumerate(meses):
                df_mes = ventas_art[ventas_art['YearMonth']==mes]
                ventas_diarias = df_mes.groupby('Fecha')['Total'].sum()
                plt.plot(ventas_diarias.index, ventas_diarias.values, label=str(mes),color=colors(i))
            plt.title(f'Ingresos diarios por mes - artículo {articulo_aleatorio} ({df_abc.loc[df_abc["Clave"]==articulo_aleatorio,"Des"].values[0]})')
            plt.xlabel('Fecha')
            plt.ylabel('Ingreso Total')
            plt.legend(title='Mes')
            plt.tight_layout()
            img_ingresos = io.BytesIO()
            plt.savefig(img_ingresos, format='png')
            plt.close()
            img_ingresos.seek(0)
            img_ing_b64 = base64.b64encode(img_ingresos.getvalue()).decode()
            grafico_ingresos_html = f'<img src="data:image/png;base64,{img_ing_b64}"/>'

            # Gráfico cantidades diarias
            plt.figure(figsize=(8,3))
            for i, mes in enumerate(meses):
                df_mes = ventas_art[ventas_art['YearMonth']==mes]
                cantidades_diarias = df_mes.groupby('Fecha')['Cantidad'].sum()
                plt.plot(cantidades_diarias.index,cantidades_diarias.values,label=str(mes),color=colors(i))
            plt.title(f'Cantidades diarias vendidas por mes - artículo {articulo_aleatorio} ({df_abc.loc[df_abc["Clave"]==articulo_aleatorio,"Des"].values[0]})')
            plt.xlabel('Fecha')
            plt.ylabel('Cantidad')
            plt.legend(title='Mes')
            plt.tight_layout()
            img_cantidades = io.BytesIO()
            plt.savefig(img_cantidades, format='png')
            plt.close()
            img_cantidades.seek(0)
            img_cant_b64 = base64.b64encode(img_cantidades.getvalue()).decode()
            grafico_cantidades_html = f'<img src="data:image/png;base64,{img_cant_b64}"/>'

            # Gráfico margen diario
            plt.figure(figsize=(8,3))
            for i, mes in enumerate(meses):
                df_mes = ventas_art[ventas_art['YearMonth']==mes]
                margen_diario = df_mes.groupby('Fecha')['Margen'].sum()
                plt.plot(margen_diario.index,margen_diario.values,label=str(mes),color=colors(i))
            plt.title(f'Margen diario por mes - artículo {articulo_aleatorio} ({df_abc.loc[df_abc["Clave"]==articulo_aleatorio,"Des"].values[0]})')
            plt.xlabel('Fecha')
            plt.ylabel('Margen')
            plt.legend(title='Mes')
            plt.tight_layout()
            img_margen = io.BytesIO()
            plt.savefig(img_margen, format='png')
            plt.close()
            img_margen.seek(0)
            img_margen_b64 = base64.b64encode(img_margen.getvalue()).decode()
            grafico_margen_html = f'<img src="data:image/png;base64,{img_margen_b64}"/>'

            extra_chart_html = f'<h3>Ingresos diarios por mes</h3>{grafico_ingresos_html}<h3>Cantidades diarias por mes</h3>{grafico_cantidades_html}<h3>Margen diario por mes</h3>{grafico_margen_html}'

        download_link = url_for('download_excel')

    return render_template_string(HTML,img_html=img_html,extra_chart_html=extra_chart_html,download_link=download_link)

@app.route('/download')
def download_excel():
    path = 'resultado_abc.xlsx'
    if os.path.exists(path):
        return send_file(path, download_name='resultado_abc.xlsx', as_attachment=True)
    else:
        return "Archivo no encontrado", 404

#if __name__ == '__main__':
#    app.run(debug=True)

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0')
