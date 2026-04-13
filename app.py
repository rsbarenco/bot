import io
import json
import os
from typing import List, Tuple

import pandas as pd
import streamlit as st
from openai import OpenAI


st.set_page_config(page_title="Bot de planilha de tênis", page_icon="👟", layout="wide")


SYSTEM_PROMPT = """
Você é um especialista em tênis de corrida.
Responda SOMENTE com base nos dados fornecidos da planilha.
Se a informação não estiver na planilha, diga claramente que não encontrou esse dado.
Não invente especificações técnicas.
Quando fizer recomendações, explique o raciocínio usando as colunas disponíveis.
Se houver ambiguidade na pergunta, aponte a limitação e diga quais colunas seriam úteis.
Responda em português do Brasil, de forma clara e objetiva.
""".strip()


def get_openai_client() -> OpenAI | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def load_dataframe(uploaded_file) -> pd.DataFrame:
    suffix = uploaded_file.name.lower().split(".")[-1]
    if suffix == "csv":
        df = pd.read_csv(uploaded_file)
    elif suffix in {"xlsx", "xlsm", "xls"}:
        df = pd.read_excel(uploaded_file)
    else:
        raise ValueError("Formato não suportado. Use .xlsx, .xls, .xlsm ou .csv")

    df = normalize_columns(df)
    return df


def build_schema_summary(df: pd.DataFrame) -> str:
    lines = []
    for col in df.columns:
        series = df[col].dropna()
        examples = series.astype(str).head(5).tolist()
        lines.append(
            f"- {col} | tipo aproximado: {str(df[col].dtype)} | exemplos: {examples}"
        )
    return "\n".join(lines)


@st.cache_data(show_spinner=False)
def dataframe_to_records_json(df: pd.DataFrame) -> str:
    cleaned = df.where(pd.notnull(df), None)
    records = cleaned.to_dict(orient="records")
    return json.dumps(records, ensure_ascii=False)


@st.cache_data(show_spinner=False)
def filter_relevant_rows(df: pd.DataFrame, question: str, max_rows: int = 20) -> pd.DataFrame:
    if not question.strip():
        return df.head(max_rows)

    terms = [t.lower() for t in question.replace(",", " ").split() if len(t) >= 3]
    if not terms:
        return df.head(max_rows)

    scores: List[Tuple[int, int]] = []
    for idx, row in df.astype(str).fillna("").iterrows():
        text = " ".join(row.values).lower()
        score = sum(1 for term in terms if term in text)
        scores.append((idx, score))

    ranked = sorted(scores, key=lambda x: x[1], reverse=True)
    best_indices = [idx for idx, score in ranked if score > 0][:max_rows]
    if not best_indices:
        return df.head(min(max_rows, len(df)))
    return df.loc[best_indices]


def ask_spreadsheet_question(client: OpenAI, question: str, df: pd.DataFrame) -> str:
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    relevant_df = filter_relevant_rows(df, question, max_rows=25)

    schema_summary = build_schema_summary(df)
    records_json = dataframe_to_records_json(relevant_df)

    user_prompt = f"""
Pergunta do usuário:
{question}

Colunas da planilha:
{list(df.columns)}

Resumo das colunas:
{schema_summary}

Linhas mais relevantes da planilha em JSON:
{records_json}

Instruções extras:
- Primeiro entenda a pergunta.
- Use apenas os dados recebidos.
- Se a pergunta pedir comparação, compare os itens encontrados.
- Se a pergunta pedir recomendação, explique por que cada modelo foi escolhido.
- Se possível, cite os nomes dos modelos exatamente como aparecem na planilha.
""".strip()

    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )

    return response.output_text.strip()


#st.title("👟 Bot de planilha de tênis de corrida")
#st.caption("Envie uma planilha e faça perguntas sobre os modelos, categorias e especificações.")

#with st.sidebar:
 #   st.header("Configuração")
 #   st.markdown("1. Crie um arquivo `.env` com sua chave da OpenAI.")
 #   st.code("OPENAI_API_KEY=sua_chave_aqui\nOPENAI_MODEL=gpt-4.1-mini")
 #   st.markdown("2. Rode o app com:")
 #   st.code("streamlit run app.py")
 #   st.markdown("3. Depois, troque o canal sem refazer a lógica: web agora, WhatsApp depois.")

#uploaded_file = st.file_uploader(
#    "Envie sua planilha (.xlsx, .xls, .xlsm ou .csv)",
#    type=["xlsx", "xls", "xlsm", "csv"],
#)

#import os
#import pandas as pd
#import streamlit as st

DEFAULT_FILE = "RunRepeat.xlsx"
# ou "data/RunRepeat.xlsx"

@st.cache_data
def load_excel_or_csv(file_or_path):
    name = file_or_path if isinstance(file_or_path, str) else file_or_path.name
    ext = os.path.splitext(name)[1].lower()

    if ext in [".xlsx", ".xls", ".xlsm"]:
        return pd.read_excel(file_or_path)
    elif ext == ".csv":
        return pd.read_csv(file_or_path)
    else:
        raise ValueError("Formato não suportado.")

st.title("Bot de planilha de tênis de corrida")

uploaded_file = st.file_uploader(
    "Trocar planilha (opcional)",
    type=["xlsx", "xls", "xlsm", "csv"]
)

source = uploaded_file if uploaded_file is not None else DEFAULT_FILE
df = load_excel_or_csv(source)

if uploaded_file is None:
    st.info(f"Usando planilha padrão: {DEFAULT_FILE}")
else:
    st.info(f"Usando planilha enviada: {uploaded_file.name}")

#st.dataframe(df.head())


#if uploaded_file is None:
#    st.info("Envie uma planilha para começar.")
#    st.stop()

#try:
#    df = load_dataframe(uploaded_file)
#except Exception as e:
#    st.error(f"Não consegui ler a planilha: {e}")
#    st.stop()

#if df.empty:
#    st.warning("A planilha foi carregada, mas está vazia.")
#    st.stop()

client = get_openai_client()
if client is None:
    st.error("Defina a variável OPENAI_API_KEY antes de usar o app.")
    st.stop()

col1, col2 = st.columns([1.2, 1])

#with col1:
#    st.subheader("Prévia da planilha")
#    st.dataframe(df, use_container_width=True, height=420)

#with col2:
#    st.subheader("Resumo")
#    st.write(f"**Linhas:** {len(df)}")
#    st.write(f"**Colunas:** {len(df.columns)}")
#    st.write("**Colunas detectadas:**")
#    st.write(", ".join([str(c) for c in df.columns]))

st.divider()
st.subheader("Pergunte sobre a planilha")
question = st.text_input(
    "Exemplos: 'Quais são os tênis mais leves?', 'Qual modelo parece melhor para rodagem?', 'Quais têm drop acima de 8 mm?'"
)

sample_questions = [
    "Quais são os modelos mais leves da planilha?",
    "Quais tênis parecem melhores para rodagem?",
    "Quais modelos têm drop acima de 8 mm?",
    "Compare os tênis de placa de carbono da planilha.",
]

selected_sample = st.selectbox("Ou escolha uma pergunta pronta", [""] + sample_questions)
if selected_sample and not question:
    question = selected_sample

if st.button("Responder", type="primary"):
    if not question.strip():
        st.warning("Digite uma pergunta.")
    else:
        with st.spinner("Analisando a planilha..."):
            try:
                answer = ask_spreadsheet_question(client, question, df)
                relevant_df = filter_relevant_rows(df, question, max_rows=15)
            except Exception as e:
                st.error(f"Erro ao consultar a IA: {e}")
            else:
                st.subheader("Resposta")
                st.write(answer)
                with st.expander("Linhas mais relevantes usadas na resposta"):
                    st.dataframe(relevant_df, use_container_width=True)
