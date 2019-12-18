// Copyright (C) 2019 VyOS maintainers and contributors
//
// This program is free software; you can redistribute it and/or modify
// in order to easy exprort images built to "external" world
// it under the terms of the GNU General Public License version 2 or later as
// published by the Free Software Foundation.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

@NonCPS

def getGitBranchName() {
    def branch = scm.branches[0].name
    return branch.split('/')[-1]
}

def getGitRepoURL() {
    return scm.userRemoteConfigs[0].url
}

def getGitRepoName() {
    return getGitRepoURL().split('/').last()
}

// Returns true if this is a custom build launched on any project fork.
// Returns false if this is build from git@github.com:vyos/<reponame>.
// <reponame> can be e.g. vyos-1x.git or vyatta-op.git
def isCustomBuild() {
    // GitHub organisation base URL
    def gitURI = 'git@github.com:vyos/' + getGitRepoName()
    def httpURI = 'https://github.com/vyos/' + getGitRepoName()

    return ! ((getGitRepoURL() == gitURI) || (getGitRepoURL() == httpURI))
}

def setDescription() {
    def item = Jenkins.instance.getItemByFullName(env.JOB_NAME)

    // build up the main description text
    def description = ""
    description += "<h2>VyOS individual package build: " + getGitRepoName().replace('.git', '') + "</h2>"

    if (isCustomBuild()) {
        description += "<p style='border: 3px dashed red; width: 50%;'>"
        description += "<b>Build not started from official Git repository!</b><br>"
        description += "<br>"
        description += "Repository: <font face = 'courier'>" + getGitRepoURL() + "</font><br>"
        description += "Branch: <font face = 'courier'>" + getGitBranchName() + "</font><br>"
        description += "</p>"
    } else {
        description += "Sources taken from Git branch: <font face = 'courier'>" + getGitBranchName() + "</font><br>"
    }

    item.setDescription(description)
    item.save()
}

/* Only keep the 10 most recent builds. */
def projectProperties = [
    [$class: 'BuildDiscarderProperty',strategy: [$class: 'LogRotator', numToKeepStr: '10']],
]

properties(projectProperties)
setDescription()

pipeline {
    agent {
        docker {
            args '--sysctl net.ipv6.conf.lo.disable_ipv6=0 -e GOSU_UID=1006 -e GOSU_GID=1006'
            image 'vyos/vyos-build:current'
            alwaysPull true
        }
    }
    options {
        disableConcurrentBuilds()
        skipDefaultCheckout()
        timeout(time: 30, unit: 'MINUTES')
        timestamps()
    }
    stages {
        stage('Fetch') {
            steps {
                script {
                    dir('build') {
                        git branch: getGitBranchName(),
                            url: getGitRepoURL()
                    }
                }
            }
        }
        stage('Build') {
            steps {
                script {
                    dir('build') {
                        def commitId = sh(returnStdout: true, script: 'git rev-parse --short=11 HEAD').trim()
                        currentBuild.description = sprintf('Git SHA1: %s', commitId[-11..-1])

                        sh 'dpkg-buildpackage -b -us -uc -tc'
                    }
                }
            }
        }
    }
    post {
        cleanup {
            deleteDir()
        }
        success {
            script {
                // archive *.deb artifact on custom builds, deploy to repo otherwise
                if ( isCustomBuild()) {
                    archiveArtifacts artifacts: '*.deb', fingerprint: true
                } else {
                    // publish build result, using SSH-dev.packages.vyos.net Jenkins Credentials
                    sshagent(['SSH-dev.packages.vyos.net']) {
                        // build up some fancy groovy variables so we do not need to write/copy
                        // every option over and over again!

                        def VYOS_REPO_PATH = '/home/sentrium/web/dev.packages.vyos.net/public_html/repositories/' + getGitBranchName() + '/'
                        def SSH_OPTS = '-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o LogLevel=ERROR'
                        def SSH_REMOTE = 'khagen@10.217.48.113'

                        echo "Uploading package(s) and updating package(s) in the repository ..."

                        files = findFiles(glob: '*.deb')
                        files.each { PACKAGE ->
                            def RELEASE = getGitBranchName()
                            def ARCH = sh(returnStdout: true, script: "dpkg-deb -f ${PACKAGE} Architecture").trim()
                            def SUBSTRING = sh(returnStdout: true, script: "dpkg-deb -f ${PACKAGE} Package").trim()
                            def SSH_DIR = '~/VyOS/' + RELEASE + '/' + ARCH
                            def ARCH_OPT = ''
                            if (ARCH != 'all')
                                ARCH_OPT = '-A ' + ARCH

                            // No need to explicitly check the return code. The pipeline
                            // will fail if sh returns a non 0 exit code
                            sh """
                                ssh ${SSH_OPTS} ${SSH_REMOTE} -t "bash --login -c 'mkdir -p ${SSH_DIR}'"
                            """
                            sh """
                                scp ${SSH_OPTS} ${PACKAGE} ${SSH_REMOTE}:${SSH_DIR}/
                            """
                            sh """
                                ssh ${SSH_OPTS} ${SSH_REMOTE} -t "uncron-add 'reprepro -v -b ${VYOS_REPO_PATH} ${ARCH_OPT} remove ${RELEASE} ${SUBSTRING}'"
                            """
                            sh """
                                ssh ${SSH_OPTS} ${SSH_REMOTE} -t "uncron-add 'reprepro -v -b ${VYOS_REPO_PATH} deleteunreferenced'"
                            """
                            sh """
                                ssh ${SSH_OPTS} ${SSH_REMOTE} -t "uncron-add 'reprepro -v -b ${VYOS_REPO_PATH} ${ARCH_OPT} includedeb ${RELEASE} ${SSH_DIR}/${PACKAGE}'"
                            """
                        }
                    }
                }
            }
        }
    }
}

