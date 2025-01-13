FROM deweycw/py310-debian

RUN apt update && apt upgrade -y 
RUN apt install wget git parallel vim gcc g++ libicu-dev -y

RUN wget https://dot.net/v1/dotnet-install.sh -O dotnet-install.sh && \
	chmod +x dotnet-install.sh && \
	./dotnet-install.sh --version latest --runtime aspnetcore

ENV PYTHONNET_RUNTIME=coreclr
ENV DOTNET_ROOT=/root/.dotnet
ENV PATH=$PATH:$DOTNET_ROOT:$DOTNET_ROOT/tools

RUN echo "alias ls='ls --color=auto'" >> ~/.bashrc
RUN echo "export PS1='\[\e[32m\]\u@\h\[\e[33m\]:\w\[\e[0m\]\$ '" >> ~/.bashrc

WORKDIR /default/workspace/CoreMS

RUN python -m pip install -U pip
RUN python -m pip install wheel
RUN python -m pip install seaborn

RUN python -m pip install coremstools
RUN python -m pip install psycopg2-binary
RUN python -m pip install pandas 